# SPDX-FileCopyrightText: 2023 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import datetime
import unittest

from core import Location, Trip
from route_planner import OpenTripPlanner


# 以下の地名、座標などは以下の著作物を改変して利用しています。
# まいどはやバスGTFS-JP、富山市、クリエイティブ・コモンズ・ライセンス　表示4.0国際
# （http://creativecommons.org/licenses/by/4.0/deed.ja）
gtfs_stations = {
    "2_1":  Location("2_1", lat=36.697688, lng=137.214331),
    "6_1":  Location("6_1",  lat=36.694054, lng=137.226118),
    "10_1": Location("10_1", lat=36.691690, lng=137.231652),
    "14_1": Location("14_1", lat=36.686273, lng=137.227487),
    "18_1": Location("18_1", lat=36.689785, lng=137.221128),
    "22_1": Location("22_1", lat=36.688628, lng=137.216664),
    "26_1": Location("26_1", lat=36.686370, lng=137.208559),
    "30_1": Location("30_1", lat=36.688185, lng=137.202896),
    "34_1": Location("34_1", lat=36.701182, lng=137.205633),
}


class OtpTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = "Bus"
        self.stations = gtfs_stations

        self.planner = OpenTripPlanner(
            endpoint="http://localhost:8080",
            ref_datetime=datetime.datetime(
                year=2024, month=2, day=1, tzinfo=datetime.timezone(datetime.timedelta(hours=+9))
            ),
            walking_meters_per_minute=80,
            modes=["TRANSIT,WALK"],
            services={"7230001002032": self.service},
        )

    async def test_up(self):
        # otp-config.json: otpFeature.ActuatorAPI = true
        # cf. http://docs.opentripplanner.org/en/v2.1.0/sandbox/ActuatorAPI/
        response = await self.planner.client.get("otp/actuators/health")
        self.assertEqual({"status": "UP"}, response)

    async def test_a_route_found(self):
        dept = (datetime.datetime(
            year=2024, month=2, day=1, hour=9, tzinfo=datetime.timezone(datetime.timedelta(hours=+9))
        ) - self.planner.ref_datetime).total_seconds() / 60
        org = self.stations["2_1"]
        dst = self.stations["22_1"]
        paths = await self.planner.plan(org=org, dst=dst, dept=dept)

        self.assertEqual([
            Trip(
                org=org,
                dst=dst,
                dept=9 * 60 + 1.0,
                arrv=9 * 60 + 33.0,
                service=self.service
            ),
        ], paths[0].trips)

    async def asyncTearDown(self):
        await self.planner.client.close()


if __name__ == '__main__':
    unittest.main()