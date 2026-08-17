# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import logging
import unittest
from datetime import date, datetime, time, timedelta

from core import EventType, Service, Stop, StopTime
from simulation import Simulation
from trip import BlockTrip, SingleTrip

logger = logging.getLogger(__name__)
BASE_DATE = date(2022, 1, 1)


def run(simulation: Simulation, until: float):
    events = []
    while simulation.peek() < until:
        _ = simulation.step()
        events.extend(simulation.event_queue.events)
    # expect nothing to happen. just let time forward.
    if simulation.env.now < until:
        simulation.env.run(until=until)
    return events


# 以下の地名、座標などは以下の著作物を改変して利用しています。
# まいどはやバスGTFS-JP、富山市、クリエイティブ・コモンズ・ライセンス　表示4.0国際
# （http://creativecommons.org/licenses/by/4.0/deed.ja）
gtfs_stations = {
    "3_1": Stop("3_1", "3_1", lat=36.695557, lng=137.220786),
    "7_1": Stop("7_1", "7_1", lat=36.696726, lng=137.227181),
    "11_1": Stop("11_1", "11_1", lat=36.690094, lng=137.231366),
    "15_1": Stop("15_1", "15_1", lat=36.685561, lng=137.225999),
    "19_1": Stop("19_1", "19_1", lat=36.692095, lng=137.220579),
    "23_0": Stop("23_0", "23_0", lat=36.688812, lng=137.213258),
    "27_1": Stop("27_1", "27_1", lat=36.683816, lng=137.207189),
    "31_1": Stop("31_1", "31_1", lat=36.69018, lng=137.203424),
    "35_1": Stop("35_1", "35_1", lat=36.702725, lng=137.207239),
}


class SingleTripTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.stops = gtfs_stations
        self.mobility_id = "mobility"

        self.simulation = Simulation(
            start_time=datetime.combine(BASE_DATE, time()),
            capacity=20,
            trips={
                self.mobility_id: SingleTrip(
                    route=...,
                    service=Service(
                        start_date=BASE_DATE,
                        end_date=BASE_DATE + timedelta(days=1),
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
                            stop=self.stops[each[0]],
                            departure=timedelta(minutes=each[1]),
                        )
                        for each in [
                            ("3_1", 543),
                            ("7_1", 548),
                            ("11_1", 558),
                            ("15_1", 562),
                            ("19_1", 566),
                            ("23_0", 574),
                            ("27_1", 578),
                            ("31_1", 583),
                            ("35_1", 590),
                        ]
                    ],
                )
            },
        )
        self.simulation.start()

    def test_overnight_trip_should_skip_past_stops_when_simulation_starts_after_midnight(
        self,
    ):
        start_date = date(year=2024, month=4, day=1)
        sim = Simulation(
            start_time=datetime.combine(start_date, time()),
            capacity=20,
            trips={
                "mobility": SingleTrip(
                    route=...,
                    service=Service(
                        start_date=start_date - timedelta(days=1),
                        end_date=start_date + timedelta(days=2),
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
                            stop=gtfs_stations["3_1"],
                            departure=timedelta(hours=23, minutes=55),
                        ),
                        StopTime(
                            stop=gtfs_stations["7_1"],
                            arrival=timedelta(hours=23, minutes=59),
                            departure=timedelta(days=1, hours=0, minutes=5),
                        ),
                        StopTime(
                            stop=gtfs_stations["11_1"],
                            arrival=timedelta(days=1, hours=0, minutes=15),
                            departure=timedelta(days=1, hours=0, minutes=15),
                        ),
                        StopTime(
                            stop=gtfs_stations["15_1"],
                            arrival=timedelta(days=1, hours=0, minutes=25),
                            departure=timedelta(days=1, hours=0, minutes=25),
                        ),
                    ],
                )
            },
        )
        sim.start()

        triggered_events = run(sim, until=1480)

        expected_operation_events = [
            (EventType.ARRIVED, 15.0, "11_1"),
            (EventType.DEPARTED, 15.0, "11_1"),
            (EventType.ARRIVED, 25.0, "15_1"),
            (EventType.DEPARTED, 25.0, "15_1"),
            (EventType.ARRIVED, 1435.0, "3_1"),
            (EventType.DEPARTED, 1435.0, "3_1"),
            (EventType.ARRIVED, 1439.0, "7_1"),
            (EventType.DEPARTED, 1445.0, "7_1"),
            (EventType.ARRIVED, 1455.0, "11_1"),
            (EventType.DEPARTED, 1455.0, "11_1"),
            (EventType.ARRIVED, 1465.0, "15_1"),
            (EventType.DEPARTED, 1465.0, "15_1"),
        ]
        actual_operation_events = [
            (
                event["eventType"],
                event["time"],
                event["details"]["location"]["locationId"],
            )
            for event in triggered_events
            if event["eventType"] in (EventType.ARRIVED, EventType.DEPARTED)
        ]
        self.assertEqual(expected_operation_events, actual_operation_events)

    def test_operation(self):
        triggered_events = run(self.simulation, until=549)
        expected_events = [
            {
                "eventType": EventType.ARRIVED,
                "time": 543.0,
                "details": {
                    "userId": None,
                    "demandId": None,
                    "mobilityId": self.mobility_id,
                    "location": {
                        "locationId": self.stops["3_1"].stop_id,
                        "lat": self.stops["3_1"].lat,
                        "lng": self.stops["3_1"].lng,
                    },
                },
            },
            {
                "eventType": EventType.DEPARTED,
                "time": 543.0,
                "details": {
                    "userId": None,
                    "demandId": None,
                    "mobilityId": self.mobility_id,
                    "location": {
                        "locationId": self.stops["3_1"].stop_id,
                        "lat": self.stops["3_1"].lat,
                        "lng": self.stops["3_1"].lng,
                    },
                },
            },
            {
                "eventType": EventType.ARRIVED,
                "time": 548.0,
                "details": {
                    "userId": None,
                    "demandId": None,
                    "mobilityId": self.mobility_id,
                    "location": {
                        "locationId": self.stops["7_1"].stop_id,
                        "lat": self.stops["7_1"].lat,
                        "lng": self.stops["7_1"].lng,
                    },
                },
            },
            {
                "eventType": EventType.DEPARTED,
                "time": 548.0,
                "details": {
                    "userId": None,
                    "demandId": None,
                    "mobilityId": self.mobility_id,
                    "location": {
                        "locationId": self.stops["7_1"].stop_id,
                        "lat": self.stops["7_1"].lat,
                        "lng": self.stops["7_1"].lng,
                    },
                },
            },
        ]
        self.assertEqual(expected_events, triggered_events)

    def test_a_user_flow(self):
        user = {
            "user_id": "U_001",
            "demand_id": "D_0001",
            "org": "3_1",
            "dst": "23_0",
            "dept": 490,
        }

        run(self.simulation, until=user["dept"])

        self.simulation.reserve_user(
            user_id=user["user_id"],
            demand_id=user["demand_id"],
            org=user["org"],
            dst=user["dst"],
            dept=user["dept"],
        )
        triggered_events = run(self.simulation, until=user["dept"] + 1)

        expected_events = [
            {
                "eventType": EventType.RESERVED,
                "time": user["dept"],
                "details": {
                    "success": True,
                    "userId": user["user_id"],
                    "demandId": user["demand_id"],
                    "mobilityId": self.mobility_id,
                    "route": [
                        {
                            "org": {
                                "locationId": self.stops[user["org"]].stop_id,
                                "lat": self.stops[user["org"]].lat,
                                "lng": self.stops[user["org"]].lng,
                            },
                            "dst": {
                                "locationId": self.stops[user["dst"]].stop_id,
                                "lat": self.stops[user["dst"]].lat,
                                "lng": self.stops[user["dst"]].lng,
                            },
                            "dept": 543.0,
                            "arrv": 574.0,
                        }
                    ],
                },
            }
        ]
        self.assertEqual(expected_events, triggered_events)

        self.simulation.dept_user(
            user_id=user["user_id"],
        )

        triggered_events = run(self.simulation, until=574.1)
        triggered_events = [
            event for event in triggered_events if event["details"]["userId"]
        ]

        expected_events = [
            {
                "eventType": EventType.DEPARTED,
                "time": 543.0,
                "details": {
                    "userId": user["user_id"],
                    "demandId": user["demand_id"],
                    "mobilityId": self.mobility_id,
                    "location": {
                        "locationId": self.stops[user["org"]].stop_id,
                        "lat": self.stops[user["org"]].lat,
                        "lng": self.stops[user["org"]].lng,
                    },
                },
            },
            {
                "eventType": EventType.ARRIVED,
                "time": 574.0,
                "details": {
                    "userId": user["user_id"],
                    "demandId": user["demand_id"],
                    "mobilityId": self.mobility_id,
                    "location": {
                        "locationId": self.stops[user["dst"]].stop_id,
                        "lat": self.stops[user["dst"]].lat,
                        "lng": self.stops[user["dst"]].lng,
                    },
                },
            },
        ]
        self.assertEqual(expected_events, triggered_events)


class BlockTripTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.reference_date = date(year=2024, month=4, day=1)
        self.stops = gtfs_stations
        self.mobility_id = "mobility"

        self.simulation = Simulation(
            start_time=datetime.combine(self.reference_date, time()),
            capacity=20,
            trips={
                self.mobility_id: BlockTrip(
                    trips=[
                        SingleTrip(
                            route=...,
                            service=Service(
                                start_date=self.reference_date,
                                end_date=self.reference_date + timedelta(days=7),
                                monday=True,
                                tuesday=True,
                                wednesday=True,
                                thursday=True,
                                friday=False,
                                saturday=False,
                                sunday=False,
                            ),
                            stop_times=[
                                StopTime(
                                    stop=self.stops[each[0]],
                                    departure=timedelta(minutes=each[1]),
                                )
                                for each in [
                                    ("3_1", 543),
                                    ("7_1", 548),
                                    ("11_1", 558),
                                    ("15_1", 562),
                                ]
                            ],
                            block_id="a",
                        ),
                        SingleTrip(
                            route=...,
                            service=Service(
                                start_date=self.reference_date,
                                end_date=self.reference_date + timedelta(days=7),
                                monday=False,
                                tuesday=False,
                                wednesday=False,
                                thursday=True,
                                friday=True,
                                saturday=True,
                                sunday=True,
                            ),
                            stop_times=[
                                StopTime(
                                    stop=self.stops[each[0]],
                                    departure=timedelta(minutes=each[1]),
                                )
                                for each in [
                                    ("19_1", 566),
                                    ("23_0", 574),
                                    ("27_1", 578),
                                    ("31_1", 583),
                                    ("35_1", 590),
                                ]
                            ],
                            block_id="a",
                        ),
                    ]
                ),
            },
        )
        self.simulation.start()

    def test_cannot_reserve_the_second_trip_only_the_first_trip_is_operating(self):
        user = {
            "user_id": "U_001",
            "demand_id": "D_0001",
            "org": "3_1",
            "dst": "23_0",
            "dept": 490,  # Monday
        }
        run(self.simulation, until=user["dept"])

        self.simulation.reserve_user(
            user_id=user["user_id"],
            demand_id=user["demand_id"],
            org=user["org"],
            dst=user["dst"],
            dept=user["dept"],
        )
        triggered_events = run(self.simulation, until=user["dept"] + 1)

        expected_events = [
            {
                "eventType": EventType.RESERVED,
                "time": user["dept"],
                "details": {
                    "success": False,
                    "userId": user["user_id"],
                    "demandId": user["demand_id"],
                },
            }
        ]
        self.assertEqual(expected_events, triggered_events)

    def test_can_reserve_the_first_trip_only_the_first_trip_is_operating(self):
        user = {
            "user_id": "U_001",
            "demand_id": "D_0001",
            "org": "3_1",
            "dst": "11_1",
            "dept": 490,  # Monday
        }
        run(self.simulation, until=user["dept"])

        self.simulation.reserve_user(
            user_id=user["user_id"],
            demand_id=user["demand_id"],
            org=user["org"],
            dst=user["dst"],
            dept=user["dept"],
        )
        triggered_events = run(self.simulation, until=user["dept"] + 1)

        expected_events = [
            {
                "eventType": EventType.RESERVED,
                "time": user["dept"],
                "details": {
                    "success": True,
                    "userId": user["user_id"],
                    "demandId": user["demand_id"],
                    "mobilityId": self.mobility_id,
                    "route": [
                        {
                            "org": {
                                "locationId": self.stops[user["org"]].stop_id,
                                "lat": self.stops[user["org"]].lat,
                                "lng": self.stops[user["org"]].lng,
                            },
                            "dst": {
                                "locationId": self.stops[user["dst"]].stop_id,
                                "lat": self.stops[user["dst"]].lat,
                                "lng": self.stops[user["dst"]].lng,
                            },
                            "dept": 543.0,
                            "arrv": 558.0,
                        }
                    ],
                },
            }
        ]
        self.assertEqual(expected_events, triggered_events)

    def test_a_user_flow_both_trips_are_in_operation(self):
        thursday = 1440 * 3
        user = {
            "user_id": "U_001",
            "demand_id": "D_0001",
            "org": "3_1",
            "dst": "23_0",
            "dept": thursday + 490.0,  # Thursday
        }
        run(self.simulation, until=user["dept"])

        self.simulation.reserve_user(
            user_id=user["user_id"],
            demand_id=user["demand_id"],
            org=user["org"],
            dst=user["dst"],
            dept=user["dept"],
        )

        triggered_events = run(self.simulation, until=user["dept"] + 1)

        expected_events = [
            {
                "eventType": EventType.RESERVED,
                "time": user["dept"],
                "details": {
                    "success": True,
                    "userId": user["user_id"],
                    "demandId": user["demand_id"],
                    "mobilityId": self.mobility_id,
                    "route": [
                        {
                            "org": {
                                "locationId": self.stops[user["org"]].stop_id,
                                "lat": self.stops[user["org"]].lat,
                                "lng": self.stops[user["org"]].lng,
                            },
                            "dst": {
                                "locationId": self.stops[user["dst"]].stop_id,
                                "lat": self.stops[user["dst"]].lat,
                                "lng": self.stops[user["dst"]].lng,
                            },
                            "dept": thursday + 543.0,
                            "arrv": thursday + 574.0,
                        }
                    ],
                },
            }
        ]
        self.assertEqual(expected_events, triggered_events)

        self.simulation.dept_user(
            user_id=user["user_id"],
        )

        triggered_events = run(self.simulation, until=thursday + 574.1)
        triggered_events = [
            event for event in triggered_events if event["details"]["userId"]
        ]

        expected_events = [
            {
                "eventType": EventType.DEPARTED,
                "time": thursday + 543.0,
                "details": {
                    "userId": user["user_id"],
                    "demandId": user["demand_id"],
                    "mobilityId": self.mobility_id,
                    "location": {
                        "locationId": self.stops[user["org"]].stop_id,
                        "lat": self.stops[user["org"]].lat,
                        "lng": self.stops[user["org"]].lng,
                    },
                },
            },
            {
                "eventType": EventType.ARRIVED,
                "time": thursday + 574.0,
                "details": {
                    "userId": user["user_id"],
                    "demandId": user["demand_id"],
                    "mobilityId": self.mobility_id,
                    "location": {
                        "locationId": self.stops[user["dst"]].stop_id,
                        "lat": self.stops[user["dst"]].lat,
                        "lng": self.stops[user["dst"]].lng,
                    },
                },
            },
        ]
        self.assertEqual(expected_events, triggered_events)


class BlockTripBoundaryTimeTestCase(unittest.TestCase):
    def test_when_boundary_stops_have_arrival_and_departure(self):
        reference_date = date(year=2024, month=4, day=1)
        service = Service(
            start_date=reference_date,
            end_date=reference_date,
            monday=True,
        )
        simulation = Simulation(
            start_time=datetime.combine(reference_date, time()),
            capacity=20,
            trips={
                "mobility": BlockTrip(
                    trips=[
                        SingleTrip(
                            route=...,
                            service=service,
                            stop_times=[
                                StopTime(
                                    stop=gtfs_stations["3_1"],
                                    departure=timedelta(minutes=543),
                                ),
                                StopTime(
                                    stop=gtfs_stations["7_1"],
                                    arrival=timedelta(minutes=548),
                                    departure=timedelta(minutes=560),
                                ),
                            ],
                            block_id="a",
                        ),
                        SingleTrip(
                            route=...,
                            service=service,
                            stop_times=[
                                StopTime(
                                    stop=gtfs_stations["7_1"],
                                    arrival=timedelta(minutes=555),
                                    departure=timedelta(minutes=566),
                                ),
                                StopTime(
                                    stop=gtfs_stations["15_1"],
                                    arrival=timedelta(minutes=574),
                                    departure=timedelta(minutes=580),
                                ),
                            ],
                            block_id="a",
                        ),
                    ]
                )
            },
        )
        simulation.start()

        triggered_events = run(simulation, until=581)
        operation_events = [
            event
            for event in triggered_events
            if event["eventType"] in (EventType.ARRIVED, EventType.DEPARTED)
        ]

        self.assertEqual(6, len(operation_events))
        self.assertEqual(574.0, operation_events[-2]["time"])
        self.assertEqual(580.0, operation_events[-1]["time"])

    def test_merge_boundaries_across_three_trips(self):
        reference_date = date(year=2024, month=4, day=1)
        service = Service(
            start_date=reference_date,
            end_date=reference_date,
            monday=True,
        )
        block_trip = BlockTrip(
            trips=[
                SingleTrip(
                    route=...,
                    service=service,
                    stop_times=[
                        StopTime(
                            stop=gtfs_stations["3_1"], departure=timedelta(minutes=543)
                        ),
                        StopTime(
                            stop=gtfs_stations["7_1"],
                            arrival=timedelta(minutes=548),
                            departure=timedelta(minutes=560),
                        ),
                    ],
                    block_id="a",
                ),
                SingleTrip(
                    route=...,
                    service=service,
                    stop_times=[
                        StopTime(
                            stop=gtfs_stations["7_1"],
                            arrival=timedelta(minutes=555),
                            departure=timedelta(minutes=566),
                        ),
                        StopTime(
                            stop=gtfs_stations["11_1"],
                            arrival=timedelta(minutes=574),
                            departure=timedelta(minutes=580),
                        ),
                    ],
                    block_id="a",
                ),
                SingleTrip(
                    route=...,
                    service=service,
                    stop_times=[
                        StopTime(
                            stop=gtfs_stations["11_1"],
                            arrival=timedelta(minutes=578),
                            departure=timedelta(minutes=585),
                        ),
                        StopTime(
                            stop=gtfs_stations["15_1"],
                            arrival=timedelta(minutes=590),
                            departure=timedelta(minutes=595),
                        ),
                    ],
                    block_id="a",
                ),
            ]
        )

        stop_times = [
            each.stop_time for each in block_trip.stop_times_at(reference_date)
        ]
        self.assertEqual(4, len(stop_times))
        self.assertEqual(timedelta(minutes=543), stop_times[0].arrival)
        self.assertEqual(timedelta(minutes=543), stop_times[0].departure)
        self.assertEqual(timedelta(minutes=548), stop_times[1].arrival)
        self.assertEqual(timedelta(minutes=566), stop_times[1].departure)
        self.assertEqual(timedelta(minutes=574), stop_times[2].arrival)
        self.assertEqual(timedelta(minutes=585), stop_times[2].departure)
        self.assertEqual(timedelta(minutes=590), stop_times[3].arrival)
        self.assertEqual(timedelta(minutes=595), stop_times[3].departure)


if __name__ == "__main__":
    unittest.main()
