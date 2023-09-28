# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest
import logging

from simulation import Simulation
from event import EventType
from mobility import ScooterParameter
from operation.reduce_fluctuations import OperatorParameter

logger = logging.getLogger(__name__)


def run(simulation: Simulation, until: float):
    events = []
    while simulation.peek() < until:
        _, triggered = simulation.step()
        events.extend(triggered)
    # expect nothing to happen. just let time forward.
    if simulation.env.now < until:
        simulation.env.run(until=until)
    return events


# 以下の地名、座標などは以下の著作物を改変して利用しています。
# まいどはやバスGTFS-JP、富山市、クリエイティブ・コモンズ・ライセンス　表示4.0国際
# （http://creativecommons.org/licenses/by/4.0/deed.ja）
gbfs_stations = {
    "2_1":  {"station_id": "2_1",  "lat": 36.697688, "lon": 137.214331},
    "6_1":  {"station_id": "6_1",  "lat": 36.694054, "lon": 137.226118},
    "10_1": {"station_id": "10_1", "lat": 36.691690, "lon": 137.231652},
    "14_1": {"station_id": "14_1", "lat": 36.686273, "lon": 137.227487},
    "18_1": {"station_id": "18_1", "lat": 36.689785, "lon": 137.221128},
    "22_1": {"station_id": "22_1", "lat": 36.688628, "lon": 137.216664},
    "26_1": {"station_id": "26_1", "lat": 36.686370, "lon": 137.208559},
    "30_1": {"station_id": "30_1", "lat": 36.688185, "lon": 137.202896},
    "34_1": {"station_id": "34_1", "lat": 36.701182, "lon": 137.205633},
}


class SimpleUserFlowCase(unittest.TestCase):
    def setUp(self) -> None:
        self.stations = gbfs_stations
        self.simulation = Simulation()
        self.simulation.setup(
            station_information=[
                self.stations["2_1"] | {"capacity": 99, "is_charging_station": True},
                self.stations["6_1"] | {"capacity": 99, "is_charging_station": True},
                self.stations["10_1"] | {"capacity": 99, "is_charging_station": True},
                self.stations["14_1"] | {"capacity": 99, "is_charging_station": True},
                self.stations["18_1"] | {"capacity": 99, "is_charging_station": True},
                self.stations["22_1"] | {"capacity": 99, "is_charging_station": True},
                self.stations["26_1"] | {"capacity": 99, "is_charging_station": True},
                self.stations["30_1"] | {"capacity": 99, "is_charging_station": True},
                self.stations["34_1"] | {"capacity": 99, "is_charging_station": True},
            ],
            free_bike_status=[
                {"bike_id": "M_001", "current_range_meters": 1200, "station_id": "2_1"},
                {"bike_id": "M_002", "current_range_meters": 800, "station_id": "2_1"}
            ],
            scooter_params=ScooterParameter(
                mobility_speed=200.0,  # [m/min] (200 m/min = 12km/h)
                charging_speed=0.003333,  # [/min] (1 / 0.003333 = 300 min = 5h)
                discharging_speed=-0.004386,  # [/min] (1 / -0.004386 = 228 min = 3h38min)
            ),
            operator_params=OperatorParameter(
                start_time=360.0,  # [min] (360 = am 6:00)
                end_time=720.0,  # [min] (720 = am 12:00)
                interval=15.0,  # [min]
                speed=1000.0,  # [m/min] (1000 m/min = 60km/h)
                loading_time=1,  # (min/mobilities)
                capacity=4,
            ),
        )

        self.simulation.start()

        self.org = {
            "locationId": self.stations["2_1"]["station_id"],
            "lat": self.stations["2_1"]["lat"],
            "lng": self.stations["2_1"]["lon"],
        }
        self.dst = {
            "locationId": self.stations["26_1"]["station_id"],
            "lat": self.stations["26_1"]["lat"],
            "lng": self.stations["26_1"]["lon"],
        }
        self.dept = 30
        self.user = {
            "user_id": "U_001",
            "org": self.org["locationId"],
            "dst": self.dst["locationId"],
        }

    def test_no_events_triggered(self):
        triggered_events = run(simulation=self.simulation, until=2880)

        self.assertEqual([], triggered_events)

    def test_success_to_reserve(self):
        _ = run(simulation=self.simulation, until=self.dept)

        self.simulation.reserve(
            user_id=self.user["user_id"],
            org=self.user["org"],
            dst=self.user["dst"],
            dept=self.dept,
        )

        triggered_events = run(simulation=self.simulation, until=31)
        expected_events = [
            {
                'eventType': EventType.RESERVED,
                'time': self.dept,
                'details': {
                    'userId': self.user["user_id"],
                    'success': True,
                    'mobilityId': 'M_001',
                    'route': [{
                        'org': self.org,
                        'dst': self.dst,
                        'dept': self.dept,
                        'arrv': 36.78891746782812
                    }]
                }
            },
        ]
        self.assertEqual(expected_events, triggered_events)

    def test_success_to_depart(self):
        _ = run(simulation=self.simulation, until=self.dept)
        self.simulation.reserve(
            user_id=self.user["user_id"],
            org=self.user["org"],
            dst=self.user["dst"],
            dept=self.dept,
        )
        _ = run(simulation=self.simulation, until=31)

        self.simulation.depart(
            user_id="U_001",
        )

        triggered_events = run(simulation=self.simulation, until=32)
        expected_events = [
            {
                'eventType': EventType.DEPARTED,
                'time': 31,
                'details': {
                    'userId': 'U_001',
                    'mobilityId': 'M_001',
                    'location': self.org,
                }
            },
        ]
        self.assertEqual(expected_events, triggered_events)

    def test_success_to_arrive(self):
        _ = run(simulation=self.simulation, until=self.dept)
        self.simulation.reserve(
            user_id=self.user["user_id"],
            org=self.user["org"],
            dst=self.user["dst"],
            dept=self.dept,
        )
        self.simulation.depart(
            user_id="U_001",
        )
        _ = run(simulation=self.simulation, until=31)

        triggered_events = run(simulation=self.simulation, until=38)
        expected_events = [
            {
                'eventType': EventType.ARRIVED,
                'time': 36.78891746782812,
                'details': {
                    'userId': 'U_001',
                    'mobilityId': 'M_001',
                    'location': self.dst,
                }
            },
        ]
        self.assertEqual(expected_events, triggered_events)

    def test_to_operate(self):
        _ = run(simulation=self.simulation, until=30)
        self.simulation.reserve(
            user_id="U_001",
            org=self.user["org"],
            dst=self.user["dst"],
            dept=self.dept,
        )
        self.simulation.reserve(
            user_id="U_002",
            org=self.user["org"],
            dst=self.user["dst"],
            dept=self.dept,
        )
        self.simulation.depart(
            user_id="U_001",
        )
        self.simulation.depart(
            user_id="U_002",
        )

        org = self.simulation.stations[self.user["org"]]
        dst = self.simulation.stations[self.user["dst"]]

        self.assertEqual(2, len(org.reservable_mobilities))
        self.assertEqual(0, len(dst.reservable_mobilities))
        run(simulation=self.simulation, until=31)
        self.assertEqual(0, len(org.reservable_mobilities))
        self.assertEqual(0, len(dst.reservable_mobilities))
        run(simulation=self.simulation, until=38)
        self.assertEqual(0, len(org.reservable_mobilities))
        self.assertEqual(2, len(dst.reservable_mobilities))
        run(simulation=self.simulation, until=360)
        self.assertEqual(0, len(org.reservable_mobilities))
        self.assertEqual(2, len(dst.reservable_mobilities))
        run(simulation=self.simulation, until=367)
        self.assertEqual(2, len(org.reservable_mobilities))
        self.assertEqual(0, len(dst.reservable_mobilities))


if __name__ == '__main__':
    unittest.main()
