# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import itertools
import typing
import logging

import networkx as nx

from core import Location, Path, Trip, MobilityNetwork


logger = logging.getLogger("planner")


class Node(typing.NamedTuple):
    location: Location
    side: str


class Network(MobilityNetwork):
    def __init__(self, service: str, mobility_meters_per_minute: float, walking_meters_per_minute: float):
        self.service = service
        self.mobility_velocity = mobility_meters_per_minute
        self.walking_velocity = walking_meters_per_minute
        self.graph = nx.Graph()

    def setup(self, locations: typing.Collection[Location]):
        self.graph.clear()

        for u, v in itertools.product(
                [Node(location=location, side="org") for location in locations],
                [Node(location=location, side="dst") for location in locations]
        ):
            u: Node
            v: Node

            # Nodes at the same location are not connected to each other.
            if u.location == v.location:
                continue

            # Nodes on the same side are not connected to each other.
            assert u.side != v.side

            # Nodes on the "org" side are only connected to nodes on the "dst" side.
            self.graph.add_edge(
                u_of_edge=u,
                v_of_edge=v,
                cost=u.location.distance(v.location) / self.mobility_velocity
            )

    def _shortest_nodes_on_path(self, org: Location, dst: Location):
        # Add temporary nodes, indicating org/ dst location.
        # Nodes on the "org" side are only connected to org location.
        # Nodes on the "dst" side are only connected to dst location.
        for node in list(self.graph.nodes):
            target = org if node.side == "org" else dst
            self.graph.add_edge(node, target, cost=node.location.distance(target) / self.walking_velocity)

        # a list of nodes in the shortest path
        nodes_on_path: typing.List[Node] = nx.shortest_path(
            G=self.graph, source=org, target=dst, weight="cost"
        )[1:-1]

        # remove temporary nodes.
        self.graph.remove_nodes_from([org, dst])

        return nodes_on_path

    def shortest_path(self, org: Location, dst: Location, dept: float):
        nodes_on_path = self._shortest_nodes_on_path(org=org, dst=dst)

        arrv = dept + org.distance(nodes_on_path[0].location) / self.walking_velocity
        trips = [Trip(
            org=org,
            dst=nodes_on_path[0].location,
            dept=dept,
            arrv=arrv,
            service="walking"
        )]

        for a, b in zip(nodes_on_path, nodes_on_path[1:]):
            dept = arrv
            arrv += a.location.distance(b.location) / self.mobility_velocity
            trips.append(Trip(
                org=a.location,
                dst=b.location,
                dept=dept,
                arrv=arrv,
                service=self.service
            ))

        trips += [Trip(
            org=nodes_on_path[-1].location,
            dst=dst,
            dept=arrv,
            arrv=arrv + nodes_on_path[-1].location.distance(dst) / self.walking_velocity,
            service="walking"
        )]

        return Path(trips)
