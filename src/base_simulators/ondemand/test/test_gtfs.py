# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest
import datetime

from core import Stop, Group, StopTime, Service, Trip
from gtfs import GtfsFlexFilesReader


class ReadFlexTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.reader = GtfsFlexFilesReader()
        self.stops = [  # stops.txt
            {
                "stop_id": "S001",
                "stop_name": "Stop1",
                "stop_lat": 137.1,
                "stop_lon": 36.1
            }, {
                "stop_id": "S002",
                "stop_name": "Stop2",
                "stop_lat": 137.2,
                "stop_lon": 36.4
            }, {
                "stop_id": "S003",
                "stop_name": "Stop3",
                "stop_lat": 137.3,
                "stop_lon": 36.9
            }
        ]
        self.location_groups = [  # location_groups.txt
            {
                "location_group_id": "G001",
                "location_id": "S001",
                "location_group_name": "Group1"
            }, {
                "location_group_id": "G001",
                "location_id": "S002",
            }, {
                "location_group_id": "G001",
                "location_id": "S003",
            },
        ]
        self.calender = [  # calender.txt
            {
                "service_id": "E001",
                "monday": "1",
                "tuesday": "",
                "wednesday": "0",
                "thursday": "1",
                "friday": "1",
                "saturday": "1",
                "sunday": "1",
                "start_date": "20200101",
                "end_date": "20241231"
            },
            {
                "service_id": "E002",
                "monday": "0",
                "tuesday": "1",
                "wednesday": "1",
                "thursday": "0",
                "friday": "0",
                "saturday": "0",
                "sunday": "0",
                "start_date": "20220101",
                "end_date": "20221231"
            }
        ]
        self.calender_dates = [  # calender_dates.txt
            {
                "service_id": "E001", "date": "20200102", "exception_type": "0",
            }, {
                "service_id": "E002", "date": "20220102", "exception_type": "1"
            }
        ]
        self.stop_times = [  # stop_times.txt
            {
                "trip_id": "T001",
                "stop_id": "G001",
                "start_pickup_dropoff_window": "7:00:00",
                "end_pickup_dropoff_window": "22:00:00"
            }, {
                "trip_id": "T002",
                "stop_id": "G001",
                "start_pickup_dropoff_window": "9:00:00",
                "end_pickup_dropoff_window": "13:00:00"
            }
        ]
        self.trips = [  # trips.txt
            {
                "trip_id": "T001",
                "service_id": "E001",
            }, {
                "trip_id": "T002",
                "service_id": "E002",
            }
        ]

    def test_successfully_parse_stops(self):
        for row in self.stops:
            self.reader._parse_stop(row)

        expected = {
            "S001": Stop(
                stop_id="S001",
                name="Stop1",
                lat=137.1,
                lng=36.1
            ),
            "S002": Stop(
                stop_id="S002",
                name="Stop2",
                lat=137.2,
                lng=36.4
            ),
            "S003": Stop(
                stop_id="S003",
                name="Stop3",
                lat=137.3,
                lng=36.9
            )
        }
        self.assertEqual(expected, self.reader.stops)

    def test_successfully_parse_location_groups(self):
        for row in self.stops:
            self.reader._parse_stop(row)
        for row in self.location_groups:
            self.reader._parse_location_groups(row)

        expected = {
            "G001": Group(
                group_id="G001",
                name="Group1",
                locations=[
                    Stop(
                        stop_id="S001",
                        name="Stop1",
                        lat=137.1,
                        lng=36.1
                    ),
                    Stop(
                        stop_id="S002",
                        name="Stop2",
                        lat=137.2,
                        lng=36.4
                    ),
                    Stop(
                        stop_id="S003",
                        name="Stop3",
                        lat=137.3,
                        lng=36.9
                    )
                ]
            )
        }
        self.assertEqual(len(expected), len(self.reader.location_groups))
        for expected_group_id, expected_group in expected.items():
            actual_group = self.reader.location_groups[expected_group_id]
            self.assertEqual(expected_group.group_id, actual_group.group_id)
            self.assertEqual(expected_group.name, actual_group.name)
            self.assertEqual(expected_group.locations, actual_group.locations)

    def test_successfully_parse_stop_times(self):
        for row in self.stops:
            self.reader._parse_stop(row)
        for row in self.location_groups:
            self.reader._parse_location_groups(row)
        for row in self.stop_times:
            self.reader._parse_stop_time(row)

        expected = {
            "T001": StopTime(
                group=self.reader.location_groups["G001"],
                start_window=datetime.timedelta(hours=7),
                end_window=datetime.timedelta(hours=22)
            ),
            "T002": StopTime(
                group=self.reader.location_groups["G001"],
                start_window=datetime.timedelta(hours=9),
                end_window=datetime.timedelta(hours=13)
            ),
        }
        self.assertEqual(expected, self.reader._stop_times)

    def test_successfully_parse_calender(self):
        for row in self.calender:
            self.reader._parse_calender(row)

        expected = {
            "E001": Service(
                start_date=datetime.date(year=2020, month=1, day=1),
                end_date=datetime.date(year=2024, month=12, day=31),
                monday=True,
                thursday=True,
                friday=True,
                saturday=True,
                sunday=True
            ),
            "E002": Service(
                start_date=datetime.date(year=2022, month=1, day=1),
                end_date=datetime.date(year=2022, month=12, day=31),
                tuesday=True,
                wednesday=True
            )
        }
        self.assertEqual(len(expected), len(self.reader._services))
        for expected_service_id, expected_service in expected.items():
            actual_service = self.reader._services[expected_service_id]
            self.assertEqual(expected_service._start_day, actual_service._start_day)
            self.assertEqual(expected_service._end_day, actual_service._end_day)
            self.assertEqual(expected_service._weekday, actual_service._weekday)

    def test_successfully_parse_calender_dates(self):
        for row in self.calender:
            self.reader._parse_calender(row)
        for row in self.calender_dates:
            self.reader._parse_calender_dates(row)

        expected = {
            "E001": Service(
                start_date=datetime.date(year=2020, month=1, day=1),
                end_date=datetime.date(year=2024, month=12, day=31),
                monday=True,
                thursday=True,
                friday=True,
                saturday=True,
                sunday=True
            ),
            "E002": Service(
                start_date=datetime.date(year=2022, month=1, day=1),
                end_date=datetime.date(year=2022, month=12, day=31),
                tuesday=True,
                wednesday=True
            )
        }

        expected["E001"].append_exception(datetime.date(year=2020, month=1, day=2), added=False)
        expected["E002"].append_exception(datetime.date(year=2022, month=1, day=2), added=True)

        for expected_service_id, expected_service in expected.items():
            actual_service = self.reader._services[expected_service_id]
            self.assertEqual(expected_service._added_exceptions, actual_service._added_exceptions)
            self.assertEqual(expected_service._removed_exceptions, actual_service._removed_exceptions)

    def test_successfully_parse_trip(self):
        for row in self.stops:
            self.reader._parse_stop(row)
        for row in self.location_groups:
            self.reader._parse_location_groups(row)
        for row in self.stop_times:
            self.reader._parse_stop_time(row)
        for row in self.calender:
            self.reader._parse_calender(row)
        for row in self.calender_dates:
            self.reader._parse_calender_dates(row)
        for row in self.trips:
            self.reader._parse_trip(row)

        expected = {
            "T001": Trip(
                service=self.reader._services["E001"],
                stop_time=self.reader._stop_times["T001"]
            ),
            "T002": Trip(
                service=self.reader._services["E002"],
                stop_time=self.reader._stop_times["T002"]
            ),
        }
        actual = self.reader.trips
        self.assertEqual(len(expected), len(actual))
        for expected_trip_id, expected_trip in expected.items():
            actual_trip = actual[expected_trip_id]
            self.assertEqual(expected_trip.service, actual_trip.service)
            self.assertEqual(expected_trip.stop_time, actual_trip.stop_time)


if __name__ == '__main__':
    unittest.main()
