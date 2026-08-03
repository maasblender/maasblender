# SPDX-FileCopyrightText: 2024 TOYOTA MOTOR CORPORATION and MaaS Blender Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import dataclasses
import logging
import typing
from functools import cached_property

import jsonschema
import yaml
from jschema.event import Event
from mblib.jschema.spec import FeatureDefinition, SpecificationResponse, TxRx
from pydantic import AnyHttpUrl
from pydantic.json_schema import JsonSchemaValue

logger = logging.getLogger(__name__)
EventType = str


@dataclasses.dataclass(init=False)
class JsonSchema:
    data: JsonSchemaValue
    current: JsonSchemaValue

    @staticmethod
    def _resolve_ref(data: JsonSchemaValue, current: JsonSchemaValue):
        if ref := current.get("$ref"):
            assert isinstance(ref, str)
            for part in ref.split("/"):
                if part == "#":
                    current = data
                else:
                    current = current.get(part)
                    if not current:
                        raise ValueError("cannot resolve $ref[%s] on %s", ref, data)
        return current

    def __init__(self, data: JsonSchemaValue, current: JsonSchemaValue = None):
        self.data = data
        self.current = self._resolve_ref(data, current or data)

    def asdict(self):
        return dataclasses.asdict(self)

    def asyaml(self):
        return yaml.safe_dump(self.asdict())

    @property
    def required(self) -> set[str]:
        return set(self.current.get("required", []))

    @property
    def properties(self) -> dict[str, JsonSchema]:
        return {
            k: JsonSchema(self.data, v)
            for k, v in self.current.get("properties", {}).items()
        }

    @property
    def additional_properties(self) -> bool:
        return self.current.get("additionalProperties", True)

    def validate(self, event: Event):
        jsonschema.validate(event.model_dump(), self.data)


class MismatchVersionError(ValueError):
    def __init__(self, versions: typing.Iterable[str]):
        details = "versions=(" + ", ".join(map(str, sorted(versions))) + ")"
        super().__init__(details)


class MismatchFutureError(ValueError):
    def __init__(self, event_type: str, modules: tuple[str, str]):
        details = f"event_type={event_type}, modules={modules}"
        super().__init__(details)


class MismatchSchemaError(ValueError):
    def __init__(self, event_type: str, modules: tuple[str, str]):
        details = f"event_type={event_type}, modules={modules}"
        super().__init__(details)


@dataclasses.dataclass(frozen=True)
class SchemaCompatibilityChecker:
    event_type: str
    tx_name: str
    rx_name: str

    def __call__(self, tx: JsonSchema, rx: JsonSchema) -> None:
        # All the fields required by receivers have to presented in sender fields
        if not rx.required <= tx.required:
            rx_req = sorted(rx.required)
            tx_req = sorted(tx.required)
            logger.error(
                f"rx.required={rx_req} must be contained in tx.required={tx_req}"
            )
            raise MismatchSchemaError(self.event_type, (self.tx_name, self.rx_name))
        for name in rx.required:
            # Check the definition of the required field
            tx_def = tx.properties.get(name)
            rx_def = rx.properties.get(name)
            if rx_def and tx_def:
                self(tx_def, rx_def)
        # logger.debug("OK:\n\ttx=%s\n\trx=%s", tx, rx)


class FeaturePairInfo(typing.NamedTuple):
    event_type: EventType
    name: str  # module name
    defs: FeatureDefinition  # feature of the module
    name_t: str  # compared module
    defs_t: FeatureDefinition  # feature of the compared module


@dataclasses.dataclass(frozen=True)
class EventValidator:
    ignore_feature: bool = False
    ignore_schema: bool = False
    ignore_in_process: bool = False
    specs: dict[str, SpecificationResponse] = dataclasses.field(default_factory=dict)

    @staticmethod
    def _inv_tx_rx(dir_: TxRx) -> TxRx:
        """get literal indicating opposite direction"""
        if dir_ == "Tx":
            return "Rx"
        else:
            return "Tx"

    def _iter_version(self) -> typing.Iterator[tuple[str, AnyHttpUrl]]:
        for module_name, spec in self.specs.items():
            yield module_name, spec.version

    def _iter_feature(
        self, dir_: TxRx
    ) -> typing.Iterator[tuple[str, EventType, FeatureDefinition]]:
        for module_name, spec in self.specs.items():
            if spec.events is not None:
                for event_type, event in spec.events.items():
                    if event.feature and event.dir == dir_:
                        yield module_name, event_type, event.feature

    def _iter_feature_on_event_type(
        self, dir_: TxRx, event_type: EventType
    ) -> typing.Iterator[tuple[str, FeatureDefinition]]:
        for module_name, spec in self.specs.items():
            if spec.events is not None:
                event = spec.events.get(event_type)
                if event and event.feature and event.dir == dir_:
                    yield module_name, event.feature

    def _iter_features_pair(self, dir_main: TxRx) -> typing.Iterator[FeaturePairInfo]:
        dir_rev = self._inv_tx_rx(dir_main)
        for name, event_type, defs in self._iter_feature(dir_main):
            for name_t, defs_t in self._iter_feature_on_event_type(dir_rev, event_type):
                yield FeaturePairInfo(event_type, name, defs, name_t, defs_t)

    def _iter_schema(
        self, dir_: TxRx
    ) -> typing.Iterator[tuple[str, EventType, JsonSchema]]:
        for name, spec in self.specs.items():
            if spec.events is not None:
                for event_type, event in spec.events.items():
                    if event.schema_ is not None and event.dir == dir_:
                        yield name, event_type, JsonSchema(event.schema_)

    def _iter_schema_on_event_type(
        self, dir_: TxRx, event_type: EventType = None
    ) -> typing.Iterator[tuple[str, JsonSchema]]:
        for name, spec in self.specs.items():
            if spec.events is not None:
                event = spec.events.get(event_type)
                if event and event.schema_ is not None and event.dir == dir_:
                    yield name, JsonSchema(event.schema_)

    def _iter_schema_pair(
        self, dir_main: TxRx
    ) -> typing.Iterator[tuple[EventType, str, str, JsonSchema, JsonSchema]]:
        dir_rev = self._inv_tx_rx(dir_main)
        for name, event_type, schema in self._iter_schema(dir_main):
            for name_r, schema_r in self._iter_schema_on_event_type(
                dir_rev, event_type
            ):
                yield event_type, name, name_r, schema, schema_r

    @cached_property
    def versions(self) -> dict[str, AnyHttpUrl]:
        return dict(self._iter_version())

    def check_versions(self):
        versions = set(self.versions.values())  # remove duplicates
        if len(versions) > 1:
            logger.error("mismatch in event schema version: %s", self.versions)
            raise MismatchVersionError([str(e) for e in sorted(versions)])

    @staticmethod
    def _contains_feature(defs: FeatureDefinition, defs_t: FeatureDefinition):
        required = set(defs.required or [])
        declared = set((defs_t.declared or []) + (defs_t.required or []))
        return declared >= required

    def check_features(self):
        if self.ignore_feature:
            return
        for e in self._iter_features_pair("Tx"):
            # print(f"{e.defs_t.declared=} >= {e.defs.required=}")
            if not self._contains_feature(e.defs, e.defs_t):
                msg = "mismatch event[%s] features, %s declared on Rx[%s] for %s required Tx[%s]"
                logger.error(
                    msg,
                    e.event_type,
                    e.defs_t.declared,
                    e.name_t,
                    e.defs.required,
                    e.name,
                )
                raise MismatchFutureError(e.event_type, (e.name, e.name_t))
        for e in self._iter_features_pair("Rx"):
            # print(f"{e.defs_t.declared=} >= {e.defs.required=}")
            if not self._contains_feature(e.defs, e.defs_t):
                msg = "mismatch event[%s] features, %s declared on Tx[%s] for %s required Rx[%s]"
                logger.error(
                    msg,
                    e.event_type,
                    e.defs_t.declared,
                    e.name_t,
                    e.defs.required,
                    e.name,
                )
                raise MismatchFutureError(e.event_type, (e.name, e.name_t))

    def check_schemas(self):
        if self.ignore_schema:
            return
        for event_type, name, name_r, schema, schema_r in self._iter_schema_pair("Rx"):
            checker = SchemaCompatibilityChecker(event_type, name_r, name)
            logger.debug("check schema 1(%s):\n%s", name, schema.asyaml())
            logger.debug("check schema 2(%s):\n%s", name_r, schema_r.asyaml())
            checker(schema_r, schema)

    @cached_property
    def _tx_schemas(self) -> dict[tuple[str, EventType], JsonSchema]:
        return {
            (name, event_type): schema
            for name, event_type, schema in self._iter_schema("Tx")
        }

    @cached_property
    def _rx_schemas(self) -> dict[tuple[str, EventType], JsonSchema]:
        return {
            (name, event_type): schema
            for name, event_type, schema in self._iter_schema("Rx")
        }

    def check_event_on_step_response(self, module_name: str, event: Event):
        if self.ignore_in_process:
            return
        schema = self._tx_schemas.get((module_name, event.eventType))
        if schema:
            try:
                schema.validate(event)
            except:
                logger.error(
                    "validation failed on step response from %s: %s", module_name, event
                )
                raise

    def check_event_on_triggered_request(self, module_name: str, event: Event):
        if self.ignore_in_process:
            return
        schema = self._rx_schemas.get((module_name, event.eventType))
        if schema:
            try:
                schema.validate(event)
            except:
                logger.error(
                    "validation failed on triggered request to %s: %s",
                    module_name,
                    event,
                )
                raise
