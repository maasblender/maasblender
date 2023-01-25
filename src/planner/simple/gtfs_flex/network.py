# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import itertools
import typing
import logging
import datetime

import networkx as nx

from core import Location, Path, Trip, MobilityNetwork
from gtfs_flex.object import Trip as gtfs_Trip, Stop, StopTime


logger = logging.getLogger("planner")


class Node(typing.NamedTuple):
    location: Stop
    side: typing.Literal["org", "dst"]
    stop_time: StopTime


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
        self.graphs: typing.Dict[datetime.date, nx.Graph] = {}
        self.trips: typing.List[gtfs_Trip] = []

    def setup(self, trips: typing.Collection[gtfs_Trip]):
        self.trips = trips

    def datetime_from(self, elapsed_minutes: float) -> datetime.datetime:
        return self.start_time + datetime.timedelta(minutes=elapsed_minutes)

    def elapsed_until(self, date_time: datetime.datetime):
        return (date_time - self.start_time).total_seconds() / 60

    def graph(self, at: datetime.date):
        if at in self.graphs:
            return self.graphs[at]
 
        self.graphs[at] = graph = nx.Graph()

        for trip in self.trips:
            if trip.service.is_operation(at):
                stop_time = trip.stop_time
                locations = stop_time.group.locations

                for u, v in itertools.product(
                        [Node(location=location, side="org", stop_time=stop_time) for location in locations],
                        [Node(location=location, side="dst", stop_time=stop_time) for location in locations]
                ):
                    u: Node
                    v: Node

                    # Nodes at the same location are not connected to each other.
                    if u.location == v.location:
                        continue

                    # Nodes on the same side are not connected to each other.
                    assert u.side != v.side

                    # Nodes on the "org" side are only connected to nodes on the "dst" side.
                    graph.add_edge(
                        u_of_edge=u,
                        v_of_edge=v,
                        cost=u.location.distance(v.location) / self.mobility_velocity
                    )
        return graph

    def _shortest_nodes_on_path(self, graph: nx.Graph, org: Location, dst: Location):
        # Add temporary nodes, indicating org/ dst location.
        # Nodes on the "org" side are only connected to org location.
        # Nodes on the "dst" side are only connected to dst location.
        for node in list(graph.nodes):
            target = org if node.side == "org" else dst
            graph.add_edge(node, target, cost=node.location.distance(target) / self.walking_velocity)

        # a list of nodes in the shortest path
        nodes_on_path: typing.List[Node] = nx.shortest_path(
            G=graph, source=org, target=dst, weight="cost"
        )[1:-1]

        # remove temporary nodes.
        graph.remove_nodes_from([org, dst])

        return nodes_on_path

    def next_available_time(self, t: float, stoptime: StopTime):
        start_window = stoptime.start_window
        end_window = stoptime.end_window
        dt = self.datetime_from(t)
        d = datetime.datetime.combine(dt.date(), datetime.time())
        s = d + start_window
        e = d + end_window
        if dt >= s and dt <= e:
            return t
        else:
            return self.elapsed_until(s)

    def shortest_path(self, org: Location, dst: Location, dept: float):
        dept_datetime = self.datetime_from(dept)
        graph = self.graph(dept_datetime.date())
        if not graph.nodes:
            return Path(trips=[Trip(org=org, dst=dst, dept=dept, arrv=float('inf'), service="not_found")])

        nodes_on_path = self._shortest_nodes_on_path(graph=graph, org=org, dst=dst)
        node0 = nodes_on_path[0]

        arrv_time = dept + org.distance(nodes_on_path[0].location) / self.walking_velocity
        trips = [Trip(
            org=org,
            dst=nodes_on_path[0].location,
            dept=dept,
            arrv=arrv_time,
            service="walking"
        )]

        dept_time = self.next_available_time(arrv_time, node0.stop_time)
        if dept_time < dept:
            # out of window (after end)
            return Path(trips=[Trip(org=org, dst=dst, dept=dept, arrv=float('inf'), service="not_found")])
        dept_time += self.waiting_bus_time
        for a, b in zip(nodes_on_path, nodes_on_path[1:]):
            arrv_time = dept_time + a.location.distance(b.location) / self.mobility_velocity
            trips.append(Trip(
                org=a.location,
                dst=b.location,
                dept=dept_time,
                arrv=arrv_time,
                service=self.service
            ))
            dept_time = arrv_time

        if arrv_time == self.next_available_time(arrv_time, node0.stop_time):
            trips += [Trip(
                org=nodes_on_path[-1].location,
                dst=dst,
                dept=arrv_time,
                arrv=arrv_time + nodes_on_path[-1].location.distance(dst) / self.walking_velocity,
                service="walking"
            )]
            return Path(trips)
        else:
            return Path(trips=[Trip(org=org, dst=dst, dept=dept, arrv=float('inf'), service="not_found")])

