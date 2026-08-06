# SPDX-FileCopyrightText: 2022 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import copy
import json
import re
import unittest
from typing import ClassVar

import pydantic
from jschema.event import Event
from jsonschema.exceptions import ValidationError
from mblib.jschema import events, spec
from validation import (
    EventValidator,
    JsonSchema,
    MismatchFutureError,
    MismatchSchemaError,
    MismatchVersionError,
    SchemaCompatibilityChecker,
)


class JsonSchemaTestCase(unittest.TestCase):
    data = json.loads("""
    {
      "$defs": {
        "ReserveEventDetails": {
          "additionalProperties": true,
          "properties": {"userId": {"title": "Userid", "type": "string"}},
          "required": ["userId"]
        }
      },
      "properties": {"details": {"$ref": "#/$defs/ReserveEventDetails"}},
      "required": ["details"]
    }
    """)

    def test_resolve_ref(self):
        dst = JsonSchema._resolve_ref(self.data, self.data["properties"]["details"])
        self.assertEqual(self.data["$defs"]["ReserveEventDetails"], dst)

    def test_validate(self):
        schema = JsonSchema(self.data)
        event = Event(eventType=events.EventType.RESERVE, time=12345.6789)
        event.details = {"userId": "hogehoge", "dummy": 987}
        print(event.model_dump())
        schema.validate(event)

    def test_validate_missing_details_userid(self):
        schema = JsonSchema(self.data)
        event = Event(eventType=events.EventType.RESERVE, time=12345.6789)
        event.details = {"user_id": "hogehoge"}
        with self.assertRaises(
            ValidationError, msg="'userId' is a required property"
        ) as cm:
            schema.validate(event)
        print(cm.exception)

    def test_validate_missing_details(self):
        schema = JsonSchema(self.data)
        event = Event(eventType=events.EventType.RESERVE, time=12345.6789)
        ptn = re.escape("'details' is a required property")
        with self.assertRaisesRegex(ValidationError, ptn) as cm:
            schema.validate(event)
        print(cm.exception)

    def test_validate_illegal_type(self):
        schema = JsonSchema(self.data)
        event = Event(eventType=events.EventType.RESERVE, time=12345.6789)
        event.details = {"userId": 3.14159, "dummy": 987}
        ptn = rf"{event.details['userId']} is not of type 'string'"
        with self.assertRaisesRegex(ValidationError, ptn) as cm:
            schema.validate(event)
        print(cm.exception)


class SchemaCompatibilityCheckerTestCase(unittest.TestCase):
    def test_ok(self):
        rx_schema = JsonSchema(
            {
                "$defs": {
                    "DemandEventDetails": {
                        "required": ["userId", "demandId", "org", "dst"]
                    }
                },
                "properties": {"details": {"$ref": "#/$defs/DemandEventDetails"}},
                "required": ["eventType", "time", "details"],
            }
        )
        tx_schema = copy.deepcopy(rx_schema)
        check = SchemaCompatibilityChecker("DEMAND", "module_from", "module_to")
        check(tx_schema, rx_schema)

    def test_ok_part(self):
        rx_schema = JsonSchema(
            {
                "$defs": {
                    "DemandEventDetails": {
                        "required": ["userId", "demandId", "org", "dst"]
                    }
                },
                "properties": {"details": {"$ref": "#/$defs/DemandEventDetails"}},
                "required": ["eventType", "time", "details"],
            }
        )
        tx_schema = copy.deepcopy(rx_schema)
        tx_schema.data["required"].append("appendix")
        tx_schema.data["$defs"]["DemandEventDetails"]["required"].append("userType")
        check = SchemaCompatibilityChecker("DEMAND", "module_from", "module_to")
        check(tx_schema, rx_schema)

    def test_ng_missing_time(self):
        rx_schema = JsonSchema(
            {
                "$defs": {
                    "DemandEventDetails": {
                        "required": ["userId", "demandId", "org", "dst"]
                    }
                },
                "properties": {"details": {"$ref": "#/$defs/DemandEventDetails"}},
                "required": ["eventType", "time", "details"],
            }
        )
        tx_schema = copy.deepcopy(rx_schema)
        tx_schema.data["required"].remove("time")
        check = SchemaCompatibilityChecker("DEMAND", "module_from", "module_to")
        ptn = re.escape(r"event_type=DEMAND, modules=('module_from', 'module_to')")
        with self.assertRaisesRegex(MismatchSchemaError, ptn) as cm:
            check(tx_schema, rx_schema)
        print(cm.exception)

    def test_ng_missing_demand(self):
        rx_schema = JsonSchema(
            {
                "$defs": {
                    "DemandEventDetails": {
                        "required": ["userId", "demandId", "org", "dst"]
                    }
                },
                "properties": {"details": {"$ref": "#/$defs/DemandEventDetails"}},
                "required": ["eventType", "time", "details"],
            }
        )
        tx_schema = copy.deepcopy(rx_schema)
        tx_schema.data["$defs"]["DemandEventDetails"]["required"].remove("demandId")
        check = SchemaCompatibilityChecker("DEMAND", "module_from", "module_to")
        ptn = re.escape(r"event_type=DEMAND, modules=('module_from', 'module_to')")
        with self.assertRaisesRegex(MismatchSchemaError, ptn) as cm:
            check(tx_schema, rx_schema)
        print(cm.exception)


class EventValidatorTestCase(unittest.TestCase):
    specs: ClassVar[dict[str, spec.SpecificationResponse]] = {
        "broker": spec.SpecificationResponse.model_validate(
            {
                "version": "https://tmc.co.jp/maas-blender/v1/base-schema.json",
                "events": {
                    "DEMAND": {
                        "dir": "Tx",
                        "schema": events.DemandEvent.model_json_schema(),
                        "feature": {"declared": ["feature_123"]},
                    },
                },
            }
        ),
        "abc_module": spec.SpecificationResponse.model_validate(
            {
                "version": "https://tmc.co.jp/maas-blender/v1/base-schema.json",
                "events": {
                    "DEMAND": {
                        "dir": "Rx",
                        "schema": events.DemandEvent.model_json_schema(),
                        "feature": {"required": ["feature_123"]},
                    },
                },
            }
        ),
        "xyz_module": spec.SpecificationResponse.model_validate(
            {
                "version": "https://tmc.co.jp/maas-blender/v1/base-schema.json",
                "events": {
                    "DEMAND": {
                        "dir": "Rx",
                        "schema": events.DemandEvent.model_json_schema(),
                        "feature": {"required": ["feature_123"]},
                    },
                    "RESERVED": {
                        "dir": "Tx",
                        "schema": events.ReservedEvent.model_json_schema(),
                        "feature": {"required": ["hogepiyo"]},
                    },
                },
            }
        ),
        "mod_a": spec.SpecificationResponse.model_validate(
            {
                "version": "https://tmc.co.jp/maas-blender/v1/base-schema.json",
                "events": {
                    "RESERVED": {
                        "dir": "Rx",
                        "schema": events.ReservedEvent.model_json_schema(),
                        "feature": {"required": ["hogepiyo"]},
                    },
                },
            }
        ),
    }

    def test_version(self):
        validator = EventValidator(specs=self.specs)
        print(validator.versions)
        validator.check_versions()

    def test_version_ng(self):
        specs = copy.deepcopy(self.specs)
        specs["abc_module"].version = pydantic.AnyHttpUrl(
            "https://tmc.co.jp/maas-blender/v2/base-schema.json"
        )
        validator = EventValidator(specs=specs)
        ptn = "https://tmc.co.jp/maas-blender/v1/base-schema.json, https://tmc.co.jp/maas-blender/v2/base-schema.json"
        with self.assertRaisesRegex(MismatchVersionError, ptn) as cm:
            validator.check_versions()
        print(cm.exception)

    def test_feature(self):
        validator = EventValidator(specs=self.specs)
        validator.check_features()

    def test_feature_ng(self):
        specs = copy.deepcopy(self.specs)
        specs["mod_B"] = spec.SpecificationResponse.model_validate(
            {
                "version": "https://z",
                "events": {
                    "DEMAND": {"dir": "Tx", "feature": {"required": ["qwerty"]}},
                },
            }
        )
        validator = EventValidator(specs=specs)
        ptn = re.escape(r"event_type=DEMAND, modules=('mod_B', 'abc_module')")
        with self.assertRaisesRegex(MismatchFutureError, ptn) as cm:
            validator.check_features()
        print(cm.exception)

    def test_schema_ng(self):
        specs = copy.deepcopy(self.specs)
        schema = events.DemandEvent.model_json_schema()
        schema["$defs"]["DemandEventDetails"]["required"].remove("userId")
        specs["mod_B"] = spec.SpecificationResponse.model_validate(
            {
                "version": "https://z",
                "events": {
                    "DEMAND": {
                        "dir": "Tx",
                        "schema": schema,
                        "feature": {"declared": ["feature_123"]},
                    },
                },
            }
        )
        validator = EventValidator(specs=specs)
        ptn = re.escape(r"event_type=DEMAND, modules=('mod_B', 'abc_module')")
        with self.assertRaisesRegex(MismatchSchemaError, ptn) as cm:
            validator.check_schemas()
        print(cm.exception)
