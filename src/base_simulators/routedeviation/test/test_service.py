# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
import unittest
import logging
from datetime import date

from core import Service

logger = logging.getLogger(__name__)


class SimpleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def test_no_services(self):
        service = Service(
            start_date=date(year=2022, month=1, day=3),
            end_date=date(year=2022, month=1, day=5),
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=1, day=2),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=1, day=3),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=1, day=4),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=1, day=5),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=1, day=6),
            )
        )

    def test_week(self):
        service = Service(
            start_date=date(year=2022, month=7, day=5),
            end_date=date(year=2022, month=7, day=13),
            monday=True,
            tuesday=False,
            wednesday=True,
            friday=True,
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=7, day=4),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=7, day=5),
            )
        )
        self.assertTrue(
            service.is_operation(
                at=date(year=2022, month=7, day=6),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=7, day=7),
            )
        )
        self.assertTrue(
            service.is_operation(
                at=date(year=2022, month=7, day=8),
            )
        )
        self.assertTrue(
            service.is_operation(
                at=date(year=2022, month=7, day=11),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=7, day=12),
            )
        )
        self.assertTrue(
            service.is_operation(
                at=date(year=2022, month=7, day=13),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=7, day=14),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=7, day=15),
            )
        )

    def test_exceptions(self):
        service = Service(
            start_date=date(year=2022, month=7, day=5),
            end_date=date(year=2022, month=7, day=13),
            monday=True,
            tuesday=False,
            wednesday=True,
            friday=True,
        )
        service.append_exception(
            exception_date=date(year=2022, month=7, day=4), added=True
        )
        service.append_exception(
            exception_date=date(year=2022, month=7, day=5), added=False
        )
        service.append_exception(
            exception_date=date(year=2022, month=7, day=6), added=False
        )
        service.append_exception(
            exception_date=date(year=2022, month=7, day=7), added=True
        )
        service.append_exception(
            exception_date=date(year=2022, month=7, day=8), added=True
        )
        self.assertTrue(
            service.is_operation(
                at=date(year=2022, month=7, day=4),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=7, day=5),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=7, day=6),
            )
        )
        self.assertTrue(
            service.is_operation(
                at=date(year=2022, month=7, day=7),
            )
        )
        self.assertTrue(
            service.is_operation(
                at=date(year=2022, month=7, day=8),
            )
        )
        self.assertTrue(
            service.is_operation(
                at=date(year=2022, month=7, day=11),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=7, day=12),
            )
        )
        self.assertTrue(
            service.is_operation(
                at=date(year=2022, month=7, day=13),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=7, day=14),
            )
        )
        self.assertFalse(
            service.is_operation(
                at=date(year=2022, month=7, day=15),
            )
        )


if __name__ == "__main__":
    unittest.main()
