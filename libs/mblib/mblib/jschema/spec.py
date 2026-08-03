# SPDX-FileCopyrightText: 2024 TOYOTA MOTOR CORPORATION
# SPDX-License-Identifier: Apache-2.0
import dataclasses
import typing
from functools import cached_property

from pydantic import AnyHttpUrl, BaseModel, Field
from pydantic.json_schema import JsonSchemaValue

TxRx = typing.Literal["Tx", "Rx"]


class FeatureDefinition(BaseModel):
    declared: list[str] | None = Field(None, title="declare to support features")
    required: list[str] | None = Field(
        None, title="declare and require to support features for other side"
    )


class EventDefinition(BaseModel):
    dir: TxRx = Field(title="incoming or outgoing")
    schema_: JsonSchemaValue | None = Field(
        None,
        title="json schema of event",
        description="if null, schema validation not supported",
        alias="schema",
    )
    feature: FeatureDefinition | None = Field(
        None,
        title="supported features of event",
        description="if null, features validation not supported",
    )

    @staticmethod
    def inspect(dir_: TxRx, event_class: type[BaseModel]):
        if hasattr(event_class, "feature"):
            feature = event_class.feature
        else:
            feature = None
        return EventDefinition(
            dir=dir_, schema=event_class.model_json_schema(), feature=feature
        )


class SpecificationResponse(BaseModel):
    version: AnyHttpUrl = Field(
        title="URI to identify corresponding API version",
        description="URI indicates event schema on base of version",
    )
    events: dict[str, EventDefinition] | None = Field(
        None,
        title="definition for supported event by type",
        description="if null, validation not supported",
    )


# class type of StepEvent or TriggeredEvent
EventClassType = typing.Any


@dataclasses.dataclass(frozen=True)
class EventSpecificationBuilder:
    events: dict[str, EventDefinition] = dataclasses.field(default_factory=dict)
    step: dataclasses.InitVar[EventClassType | None] = None
    triggered: dataclasses.InitVar[EventClassType | None] = None

    def __post_init__(self, step: EventClassType, triggered: EventClassType):
        # set event specification of step API response
        self._set_events("Tx", step)
        # set event specification of triggered API request
        self._set_events("Rx", triggered)

    @staticmethod
    def _extract_element_type_of_union(event_class: EventClassType):
        if event_class:
            event_classes = getattr(event_class, "__args__", None)
            if event_classes:
                yield from event_classes
            else:  # if only one event type
                yield event_class

    def _set_events(self, dir_: TxRx, event_class: EventClassType):
        for e in self._extract_element_type_of_union(event_class):
            schema = e.model_json_schema()
            event_type = schema["properties"]["eventType"]["const"]
            self.events[event_type] = EventDefinition(dir=dir_, schema=schema)

    def set_feature(
        self,
        event_type: typing.Any,
        *,
        declared: list[str] | None = None,
        required: list[str] | None = None,
    ) -> None:
        """set feature definition for step or triggered event specification"""
        feature = FeatureDefinition(declared=declared, required=required)
        self.events[str(event_type)].feature = feature

    def get_specification_response(self, *, version: str) -> SpecificationResponse:
        """get specification response data"""
        if self.events:
            return SpecificationResponse(version=version, events=self.events)
        else:
            return SpecificationResponse(version=version)

    @property
    def schemas(self) -> dict[str, JsonSchemaValue | None]:
        return {event_type: e.schema_ for event_type, e in self.events.items()}

    @cached_property
    def event_types_of_triggered(self) -> set[str]:
        return set(self.events.keys())
