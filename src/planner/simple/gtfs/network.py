# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import typing
import logging
import datetime

import networkx as nx
from networkx.exception import NetworkXNoPath

from core import Location, Path, Trip, MobilityNetwork
from gtfs.object import Trip as gtfs_Trip, StopTimeWithDatetime as StopTime

logger = logging.getLogger("planner")


class SchedulePoint(typing.NamedTuple):
    stop: Location
    time: datetime.datetime
    side: typing.Literal["org", "dst"]


def add_nodes(graph: nx.DiGraph, stop_times: typing.Sequence[StopTime]):
    for source, target in zip(stop_times, stop_times[1:]):
        # The "org" side is interested in departure times.
        graph.add_edge(
            u_of_edge=SchedulePoint(source.stop, source.departure, side="org"),
            v_of_edge=SchedulePoint(target.stop, target.departure, side="org"),
            weight=(target.departure - source.departure).total_seconds() / 60
        )
        # The "dst" side is interested in arrival times.
        graph.add_edge(
            u_of_edge=SchedulePoint(source.stop, source.departure, side="org"),
            v_of_edge=SchedulePoint(target.stop, target.departure, side="dst"),
            weight=(target.arrival - source.departure).total_seconds() / 60
        )


class Network(MobilityNetwork):
    def __init__(
            self,
            service: str,
            walking_meters_per_minute: float,
            start_time: datetime.datetime,
            max_waiting_bus_time: float = 0
    ):
        self.service = service
        self.start_time = start_time
        self.walking_velocity = walking_meters_per_minute
        self.max_waiting_bus_time = max_waiting_bus_time
        self.graphs: typing.Dict[datetime.date, nx.DiGraph] = {}
        self.trips: typing.List[gtfs_Trip] = []

    def setup(self, trips: typing.Collection[gtfs_Trip]):
        self.trips = list(trips)

    def datetime_from(self, elapsed_minutes: float):
        return self.start_time + datetime.timedelta(minutes=elapsed_minutes)

    def elapsed_until(self, date_time: datetime.datetime):
        return (date_time - self.start_time).total_seconds() / 60

    def graph(self, at: datetime.date):
        if at in self.graphs:
            return self.graphs[at]

        self.graphs[at] = graph = nx.DiGraph()

        for trip in self.trips:
            if trip.service.is_operation(at):
                add_nodes(graph, trip.stop_times(at))

        return graph

        # ToDo: Allow transfer to another Trip

    def _nodes_on_shortest_path(
            self, graph: nx.DiGraph, org: Location, dst: Location, dept: datetime.datetime
    ) -> typing.List[SchedulePoint]:
        # Add temporary nodes, indicating org/ dst location.
        # Nodes on the "org" side are only connected to org location.
        # Nodes on the "dst" side are only connected to dst location.
        for node in list(graph.nodes):
            node: SchedulePoint

            if node.side == "dst":
                walking_duration = node.stop.distance(dst) / self.walking_velocity

                # weight = walking duration
                graph.add_edge(u_of_edge=node, v_of_edge=dst, weight=walking_duration)

            elif node.side == "org":
                walking_duration = node.stop.distance(org) / self.walking_velocity

                # Ignore nodes that are not on time for departure.
                if node.time < dept + datetime.timedelta(minutes=walking_duration):
                    continue

                weight = (node.time - dept).total_seconds() / 60.0

                # Ignore nodes whose waiting time at the stop exceeds "max_waiting_bus_time"
                if self.max_waiting_bus_time and weight - walking_duration > self.max_waiting_bus_time:
                    continue

                # weight = waiting time at the stop + walking duration
                graph.add_edge(u_of_edge=org, v_of_edge=node, weight=weight)

        # Depending on the dept time, org node may not be added to the temporary graph.
        graph.add_node(org)

        # There may be many shortest paths between the source and target.
        # The station nearest to the source is preferentially selected.
        # Actually, a single list of nodes in the shortest path.
        try:
            return sorted(
                nx.all_shortest_paths(
                    G=graph,
                    source=org,
                    target=dst,
                    weight="weight"
                ),
                key=lambda path: path[1].stop.distance(org)
            )[0][1:-1]
        except NetworkXNoPath:
            return []
        finally:
            # remove temporary nodes.
            graph.remove_nodes_from([org, dst])

    def nodes_on_shortest_path(
            self, org: Location, dst: Location, dept: float
    ) -> typing.List[SchedulePoint]:

        dept = self.datetime_from(dept)
        # graphs in the other day may contain more appropriate paths
        for graph in [
            self.graph(dept.date() - datetime.timedelta(days=1)),
            self.graph(dept.date()),
            self.graph(dept.date() + datetime.timedelta(days=1))
        ]:
            nodes_on_path = self._nodes_on_shortest_path(graph, org, dst, dept)
            if nodes_on_path:
                return nodes_on_path

        return []

    def shortest_path(self, org: Location, dst: Location, dept: float):
        if not (nodes_on_path := self.nodes_on_shortest_path(org, dst, dept)):
            return Path(trips=[Trip(org=org, dst=dst, dept=dept, arrv=float('inf'), service="not_found")])

        dept_stop, dept_time = nodes_on_path[0].stop, self.elapsed_until(nodes_on_path[0].time)
        arrv_stop, arrv_time = nodes_on_path[-1].stop, self.elapsed_until(nodes_on_path[-1].time)

        return Path(
            [Trip(
                org=org,
                dst=dept_stop,
                dept=dept,
                arrv=dept + org.distance(dept_stop) / self.walking_velocity,
                service="walking"
            )] + [Trip(
                org=dept_stop,
                dst=arrv_stop,
                dept=dept_time,
                arrv=arrv_time,
                service=self.service
            )] + [Trip(
                org=arrv_stop,
                dst=dst,
                dept=arrv_time,
                arrv=arrv_time + arrv_stop.distance(dst) / self.walking_velocity,
                service="walking"
            )]
        )
