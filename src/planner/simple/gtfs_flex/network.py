# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import datetime
import itertools
import logging
import typing

import networkx as nx
from core import Location, MobilityNetwork, Path, Trip
from networkx.exception import NetworkXNoPath

from gtfs_flex.object import Stop, StopTime
from gtfs_flex.object import Trip as gtfs_Trip

logger = logging.getLogger(__name__)


class Node(typing.NamedTuple):
    stop: Stop
    side: typing.Literal["org", "dst"]


class Network(MobilityNetwork):
    def __init__(
        self,
        service: str,
        start_time: datetime.datetime,
        mobility_meters_per_minute: float,
        walking_meters_per_minute: float,
        expected_waiting_time: float,
    ):
        self.service = service
        self.start_time = start_time
        self.mobility_velocity = mobility_meters_per_minute
        self.walking_velocity = walking_meters_per_minute
        self.waiting_bus_time = expected_waiting_time
        self.graphs: dict[datetime.date, nx.DiGraph] = {}
        self.trips: list[gtfs_Trip] = []

    def setup(self, trips: typing.Collection[gtfs_Trip]):
        self.trips = trips

    def datetime_from(self, elapsed_minutes: float) -> datetime.datetime:
        return self.start_time + datetime.timedelta(minutes=elapsed_minutes)

    def elapsed_until(self, date_time: datetime.datetime):
        return (date_time - self.start_time).total_seconds() / 60

    def graph_from_stops(self, stops: list[Stop]):
        graph = nx.DiGraph()
        for u, v in itertools.product(
            [Node(stop=stop, side="org") for stop in stops],
            [Node(stop=stop, side="dst") for stop in stops],
        ):
            u: Node
            v: Node

            # Nodes at the same location are not connected to each other.
            if u.stop == v.stop:
                continue

            # Nodes on the same side are not connected to each other.
            assert u.side != v.side

            # Nodes on the "org" side are only connected to nodes on the "dst" side.
            graph.add_edge(
                u_of_edge=u,
                v_of_edge=v,
                cost=u.stop.distance(v.stop) / self.mobility_velocity,
            )
        return graph

    def graph(self, at: datetime.date):
        if at in self.graphs:
            return self.graphs[at]
        prev = at - datetime.timedelta(days=1)
        next_ = at + datetime.timedelta(days=1)

        self.graphs[at] = graph = {}

        for trip in self.trips:
            trip: gtfs_Trip

            stop_time = trip.stop_time
            stops = stop_time.group.locations
            assert stop_time.start_window < stop_time.end_window
            if trip.service.is_operation(at):
                graph[stop_time] = self.graph_from_stops(stops)
            if trip.service.is_operation(
                prev
            ) and trip.stop_time.end_window > datetime.timedelta(days=1):
                # add nodes for after midnight trip
                stop_time = StopTime(
                    group=stop_time.group,
                    start_window=datetime.timedelta(minutes=0),
                    end_window=stop_time.end_window - datetime.timedelta(days=1),
                )
                graph[stop_time] = self.graph_from_stops(stops)
            if trip.service.is_operation(next_):
                stop_time = StopTime(
                    group=stop_time.group,
                    start_window=stop_time.start_window + datetime.timedelta(days=1),
                    end_window=stop_time.end_window + datetime.timedelta(days=1),
                )
                graph[stop_time] = self.graph_from_stops(stops)
        return graph

    def _nodes_on_shortest_path(
        self, graph: nx.DiGraph, org: Location, dst: Location
    ) -> tuple[list[Node], list[float]]:
        # Add temporary nodes, indicating org/ dst location.
        for node in list(graph.nodes):
            node: Node
            if node.side == "org":
                graph.add_edge(
                    org, node, cost=org.distance(node.stop) / self.walking_velocity
                )
            else:
                graph.add_edge(
                    node, dst, cost=node.stop.distance(dst) / self.walking_velocity
                )

        # a list of nodes in the shortest path
        try:
            path = nx.shortest_path(graph, source=org, target=dst, weight="cost")
            costs = [graph.edges[u, v]["cost"] for u, v in itertools.pairwise(path)]
            return path[1:-1], costs
        except NetworkXNoPath:
            return [], []
        finally:
            # remove temporary nodes.
            graph.remove_nodes_from([org, dst])

    def expected_arrival(
        self,
        path: list[Node],
        costs: list[float],
        dept: float,
        today: datetime.datetime,
        stop_time: StopTime,
    ) -> list[float]:
        assert len(path) == 2
        assert len(costs) == 3
        arrv0 = dept + costs[0]
        dept1 = arrv0
        start_window = today + stop_time.start_window
        end_window = today + stop_time.end_window
        if self.datetime_from(dept1) > end_window:
            # maybe next day's trip
            start_window = start_window + datetime.timedelta(days=1)
            end_window = end_window + datetime.timedelta(days=1)
        # bus trip includes waiting time
        # but dept1 is arrival time to the bus stop for optimal reservation
        if self.datetime_from(dept1) >= start_window:
            arrv1 = dept1 + self.waiting_bus_time + costs[1]
        else:
            # also bus trip includes waiting time until service start
            arrv1 = self.elapsed_until(start_window) + self.waiting_bus_time + costs[1]
        if self.datetime_from(arrv1) < end_window:
            dept2 = arrv1
            arrv2 = dept2 + costs[2]
            return [dept, arrv0, dept1, arrv1, dept2, arrv2]
        else:
            # arrival after service end
            return []

    def nodes_on_shortest_path(
        self, org: Location, dst: Location, dept: float
    ) -> tuple[list[Node], list[float]]:
        today = self.datetime_from(dept).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        opt_dept_arrv = None
        opt_nodes = None
        for stop_time, graph in self.graph(today.date()).items():
            stop_time: StopTime
            graph: nx.DiGraph
            # search per trip
            if (
                graph
                and graph.nodes
                and today + stop_time.end_window > self.datetime_from(dept)
            ):
                path, costs = self._nodes_on_shortest_path(graph, org, dst)
                if path:
                    dept_arrv = self.expected_arrival(
                        path, costs, dept, today, stop_time
                    )
                    if dept_arrv and (
                        opt_dept_arrv is None or dept_arrv[-1] < opt_dept_arrv[-1]
                    ):
                        opt_dept_arrv = dept_arrv
                        opt_nodes = path
        return opt_nodes, opt_dept_arrv

    def shortest_path(self, org: Location, dst: Location, dept: float):
        path, dept_arrv = self.nodes_on_shortest_path(org=org, dst=dst, dept=dept)
        if not path:
            return Path(
                trips=[
                    Trip(
                        org=org,
                        dst=dst,
                        dept=dept,
                        arrv=float("inf"),
                        service="not_found",
                    )
                ]
            )
        assert len(path) == 2
        assert len(dept_arrv) == 6

        trips = [
            Trip(
                org=org,
                dst=path[0].stop,
                dept=dept,
                arrv=dept_arrv[1],
                service="walking",
            ),
            Trip(
                org=path[0].stop,
                dst=path[1].stop,
                dept=dept_arrv[2],
                arrv=dept_arrv[3],
                service=self.service,
            ),
            Trip(
                org=path[1].stop,
                dst=dst,
                dept=dept_arrv[4],
                arrv=dept_arrv[5],
                service="walking",
            ),
        ]
        return Path(trips)
