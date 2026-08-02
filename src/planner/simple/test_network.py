# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import datetime
import unittest

from core import Location, Path, Trip, WalkingNetwork
from gbfs.network import Network as GbfsNetwork
from gtfs.network import Network as GtfsNetwork
from gtfs.object import Service, StopTime
from gtfs.object import Trip as gtfs_Trip
from gtfs_flex.network import Network as GtfsFlexNetwork
from gtfs_flex.object import Group as flex_Group
from gtfs_flex.object import Service as flex_Service
from gtfs_flex.object import Stop as flex_Stop
from gtfs_flex.object import StopTime as flex_StopTime
from gtfs_flex.object import Trip as flex_Trip

BASE_DATE = datetime.date(2022, 1, 1)


# 以下の地名、座標などは以下の著作物を改変して利用しています。
# まいどはやバスGTFS-JP、富山市、クリエイティブ・コモンズ・ライセンス　表示4.0国際
# （http://creativecommons.org/licenses/by/4.0/deed.ja）
locations = {
    "1_1": Location(id_="1_1", lat=36.699941, lng=137.212183),
    "5_1": Location(id_="5_1", lat=36.692495, lng=137.223181),
    "9_1": Location(id_="9_1", lat=36.693708, lng=137.231302),
    "13_1": Location(id_="13_1", lat=36.686913, lng=137.228431),
    "17_1": Location(id_="17_1", lat=36.686592, lng=137.221622),
    "21_1": Location(id_="21_1", lat=36.689415, lng=137.218713),
    "25_1": Location(id_="25_1", lat=36.688971, lng=137.210680),
    "29_1": Location(id_="29_1", lat=36.685340, lng=137.202158),
    "33_1": Location(id_="33_1", lat=36.699350, lng=137.205897),
}

gbfs_stations = {
    "2_1": Location(id_="2_1", lat=36.697688, lng=137.214331),
    "6_1": Location(id_="6_1", lat=36.694054, lng=137.226118),
    "10_1": Location(id_="10_1", lat=36.691690, lng=137.231652),
    "14_1": Location(id_="14_1", lat=36.686273, lng=137.227487),
    "18_1": Location(id_="18_1", lat=36.689785, lng=137.221128),
    "22_1": Location(id_="22_1", lat=36.688628, lng=137.216664),
    "26_1": Location(id_="26_1", lat=36.686370, lng=137.208559),
    "30_1": Location(id_="30_1", lat=36.688185, lng=137.202896),
    "34_1": Location(id_="34_1", lat=36.701182, lng=137.205633),
}

gtfs_stations = {
    "3_1": Location(id_="3_1", lat=36.695557, lng=137.220786),
    "7_1": Location(id_="7_1", lat=36.696726, lng=137.227181),
    "11_1": Location(id_="11_1", lat=36.690094, lng=137.231366),
    "15_1": Location(id_="15_1", lat=36.685561, lng=137.225999),
    "19_1": Location(id_="19_1", lat=36.692095, lng=137.220579),
    "23_0": Location(id_="23_1", lat=36.688812, lng=137.213258),
    "27_1": Location(id_="27_1", lat=36.683816, lng=137.207189),
    "31_1": Location(id_="31_1", lat=36.69018, lng=137.203424),
    "35_1": Location(id_="35_1", lat=36.702725, lng=137.207239),
}

# Consider to standardize `flex_Stop` on `Location`
gtfs_flex_stations = {
    "4_1": flex_Stop(id_="4_1", lat=36.693502, lng=137.221182),
    "8_1": flex_Stop(id_="8_1", lat=36.69584, lng=137.229556),
    "12_1": flex_Stop(id_="12_1", lat=36.687999, lng=137.23096),
    "16_1": flex_Stop(id_="16_1", lat=36.68531, lng=137.224181),
    "20_1": flex_Stop(id_="20_1", lat=36.691131, lng=137.218582),
    "24_0": flex_Stop(id_="24_1", lat=36.688624, lng=137.213717),
    "28_1": flex_Stop(id_="28_1", lat=36.684078, lng=137.204254),
    "32_1": flex_Stop(id_="32_1", lat=36.695193, lng=137.204635),
    "36_1": flex_Stop(id_="36_1", lat=36.70177, lng=137.209607),
}


class WalkingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.walking_velocity = 80.0

        self.network = WalkingNetwork(
            "walking", walking_meters_per_minute=self.walking_velocity
        )

    def test_correct_path(self):
        org = locations["1_1"]
        dst = locations["5_1"]
        path = self.network.shortest_path(org, dst, dept=10)

        expected = Path(
            [
                Trip(
                    org=locations["1_1"],
                    dst=locations["5_1"],
                    dept=10,
                    arrv=10 + org.distance(dst) / self.walking_velocity,
                    service="walking",
                )
            ]
        )
        self.assertEqual(expected, path)


class GbfsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service_name = "GbfsMobility"
        self.walking_velocity = 80.0
        self.mobility_velocity = 200.0
        self.stations = gbfs_stations

        self.network = GbfsNetwork(
            service=self.service_name,
            walking_meters_per_minute=self.walking_velocity,
            mobility_meters_per_minute=self.mobility_velocity,
        )
        self.network.setup(self.stations.values())

    def test_successfully_created_graph(self):
        locations_length = len(locations)
        self.assertEqual(locations_length * 2, len(self.network.graph.nodes))
        self.assertEqual(
            locations_length * (locations_length - 1), len(self.network.graph.edges)
        )

    def test_correct_path_case(self):
        org = locations["1_1"]
        dst = locations["21_1"]

        path = self.network.shortest_path(org, dst, 10)

        expected = Path(
            [
                Trip(
                    org=org,
                    dst=self.stations["2_1"],
                    dept=10,
                    arrv=10
                    + org.distance(self.stations["2_1"]) / self.walking_velocity,
                    service="walking",
                ),
                Trip(
                    org=self.stations["2_1"],
                    dst=self.stations["22_1"],
                    dept=10
                    + org.distance(self.stations["2_1"]) / self.walking_velocity,
                    arrv=10
                    + org.distance(self.stations["2_1"]) / self.walking_velocity
                    + self.stations["2_1"].distance(self.stations["22_1"])
                    / self.mobility_velocity,
                    service=self.service_name,
                ),
                Trip(
                    org=self.stations["22_1"],
                    dst=dst,
                    dept=10
                    + org.distance(self.stations["2_1"]) / self.walking_velocity
                    + self.stations["2_1"].distance(self.stations["22_1"])
                    / self.mobility_velocity,
                    arrv=10
                    + org.distance(self.stations["2_1"]) / self.walking_velocity
                    + self.stations["2_1"].distance(self.stations["22_1"])
                    / self.mobility_velocity
                    + self.stations["22_1"].distance(dst) / self.walking_velocity,
                    service="walking",
                ),
            ]
        )

        self.assertEqual(expected, path)


class GtfsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service_name = "GtfsMobility"
        self.walking_velocity = 80
        self.network = GtfsNetwork(
            service=self.service_name,
            walking_meters_per_minute=self.walking_velocity,
            start_time=datetime.datetime.combine(BASE_DATE, datetime.time()),
        )
        self.stations = gtfs_stations
        schedule: list[tuple[Location, float]] = [
            (self.stations["3_1"], 543),
            (self.stations["7_1"], 548),
            (self.stations["11_1"], 558),
            (self.stations["15_1"], 562),
            (self.stations["19_1"], 566),
            (self.stations["23_0"], 574),
            (self.stations["27_1"], 578),
            (self.stations["31_1"], 583),
            (self.stations["35_1"], 590),
        ]

        trip = gtfs_Trip(
            service=Service(
                start_date=BASE_DATE,
                end_date=BASE_DATE + datetime.timedelta(days=1),
                monday=True,
                tuesday=True,
                wednesday=True,
                thursday=True,
                friday=True,
                saturday=True,
                sunday=True,
            ),
            stop_times=[
                StopTime(
                    stop=location,
                    arrival=datetime.timedelta(minutes=time),
                    departure=datetime.timedelta(minutes=time),
                )
                for location, time in schedule
            ],
        )
        self.network.setup(trips=[trip])

    def test_correct_path_case(self):
        org = locations["1_1"]
        dst = locations["21_1"]
        path = self.network.shortest_path(org, dst, 530.0)

        expected = Path(
            [
                Trip(
                    org=org,
                    dst=self.stations["3_1"],
                    dept=530.0,
                    arrv=530.0
                    + org.distance(self.stations["3_1"]) / self.walking_velocity,
                    service="walking",
                ),
                Trip(
                    org=self.stations["3_1"],
                    dst=self.stations["7_1"],
                    dept=543.0,
                    arrv=548.0,
                    service=self.service_name,
                ),
                Trip(
                    org=self.stations["7_1"],
                    dst=dst,
                    dept=548.0,
                    arrv=548
                    + self.stations["7_1"].distance(dst) / self.walking_velocity,
                    service="walking",
                ),
            ]
        )

        self.assertEqual(expected, path)


class OndemandBusTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service_name = "GtfsFlexMobility"
        self.walking_velocity = 80
        self.mobility_velocity = 200
        self.expected_waiting_time = 10
        self.start_window = 9 * 60
        self.end_window = self.start_window + 12 * 60
        self.network = GtfsFlexNetwork(
            service=self.service_name,
            walking_meters_per_minute=self.walking_velocity,
            mobility_meters_per_minute=self.mobility_velocity,
            expected_waiting_time=self.expected_waiting_time,
            start_time=datetime.datetime.combine(BASE_DATE, datetime.time()),
        )
        self.stations = gtfs_flex_stations
        self.network.setup(
            [
                flex_Trip(
                    service=flex_Service(
                        start_date=BASE_DATE,
                        end_date=BASE_DATE + datetime.timedelta(days=1),
                        monday=True,
                        tuesday=True,
                        wednesday=True,
                        thursday=True,
                        friday=True,
                        saturday=True,
                        sunday=True,
                    ),
                    stop_time=flex_StopTime(
                        group=flex_Group(
                            group_id="g0",
                            name="g0",
                            locations=[
                                flex_Stop(
                                    id_=location.id_,
                                    name=location.id_,
                                    lat=location.lat,
                                    lng=location.lng,
                                )
                                for location in self.stations.values()
                            ],
                        ),
                        start_window=datetime.timedelta(minutes=self.start_window),
                        end_window=datetime.timedelta(minutes=self.end_window),
                    ),
                )
            ]
        )

    def test_no_path_case_not_available(self):
        org = locations["1_1"]
        dst = locations["21_1"]
        dept = self.start_window + 60 + 2 * 24 * 60  # 1day after

        path = self.network.shortest_path(org, dst, dept)

        self.assertEqual(
            Path(
                trips=[
                    Trip(
                        org=org,
                        dst=dst,
                        dept=dept,
                        arrv=float("inf"),
                        service="not_found",
                    )
                ]
            ),
            path,
        )

    def test_correct_path_case(self):
        org = locations["1_1"]
        dst = locations["21_1"]
        dept = self.start_window + 60

        path = self.network.shortest_path(org, dst, dept)

        expected = Path(
            [
                Trip(
                    org=org,
                    dst=self.stations["36_1"],
                    dept=dept,
                    arrv=dept
                    + org.distance(self.stations["36_1"]) / self.walking_velocity,
                    service="walking",
                ),
                Trip(
                    org=self.stations["36_1"],
                    dst=self.stations["20_1"],
                    dept=dept
                    + org.distance(self.stations["36_1"]) / self.walking_velocity,
                    arrv=dept
                    + org.distance(self.stations["36_1"]) / self.walking_velocity
                    + self.stations["36_1"].distance(self.stations["20_1"])
                    / self.mobility_velocity
                    + self.expected_waiting_time,
                    service=self.service_name,
                ),
                Trip(
                    org=self.stations["20_1"],
                    dst=dst,
                    dept=dept
                    + org.distance(self.stations["36_1"]) / self.walking_velocity
                    + self.stations["36_1"].distance(self.stations["20_1"])
                    / self.mobility_velocity
                    + self.expected_waiting_time,
                    arrv=dept
                    + org.distance(self.stations["36_1"]) / self.walking_velocity
                    + self.stations["36_1"].distance(self.stations["20_1"])
                    / self.mobility_velocity
                    + self.stations["20_1"].distance(dst) / self.walking_velocity
                    + self.expected_waiting_time,
                    service="walking",
                ),
            ]
        )

        self.assertEqual(expected, path)


if __name__ == "__main__":
    unittest.main()
