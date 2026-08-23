from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class SchemaValidationError(ValueError):
    """Raised when untrusted input does not match an application schema."""


def _object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise SchemaValidationError("expected an object")
    return value


def _required(payload: dict[str, Any], name: str) -> Any:
    if name not in payload:
        raise SchemaValidationError(f"missing field: {name}")
    return payload[name]


def _integer(value: Any) -> int:
    if type(value) is not int:
        raise SchemaValidationError("expected an integer")
    return value


def _optional_string(
    payload: dict[str, Any], name: str, maximum: int
) -> str | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > maximum:
        raise SchemaValidationError(f"invalid string field: {name}")
    return value


def _date_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise SchemaValidationError("expected an ISO datetime")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise SchemaValidationError("expected an ISO datetime") from exc


@dataclass(frozen=True, slots=True)
class NamedReference:
    id: int | None = None
    name: str | None = None

    @classmethod
    def from_payload(cls, value: Any) -> NamedReference:
        payload = _object(value)
        raw_id = payload.get("id")
        reference_id = None if raw_id is None else _integer(raw_id)
        return cls(
            id=reference_id,
            name=_optional_string(payload, "name", 200),
        )

    def to_payload(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name}


def _references(payload: dict[str, Any], name: str) -> list[NamedReference]:
    value = payload.get(name, [])
    if not isinstance(value, list) or len(value) > 32:
        raise SchemaValidationError(f"invalid reference list: {name}")
    return [NamedReference.from_payload(item) for item in value]


@dataclass(frozen=True, slots=True)
class UpstreamSubstitution:
    id: int
    type: int
    start: datetime
    end: datetime
    oldSubject: str | None = None
    newSubject: str | None = None
    oldRooms: list[NamedReference] = field(default_factory=list)
    newRooms: list[NamedReference] = field(default_factory=list)
    oldTeachers: list[NamedReference] = field(default_factory=list)
    newTeachers: list[NamedReference] = field(default_factory=list)
    oldClasses: list[NamedReference] = field(default_factory=list)
    newClasses: list[NamedReference] = field(default_factory=list)
    comment: str | None = None

    @classmethod
    def from_payload(cls, value: Any) -> UpstreamSubstitution:
        payload = _object(value)
        return cls(
            id=_integer(_required(payload, "id")),
            type=_integer(_required(payload, "type")),
            start=_date_time(_required(payload, "start")),
            end=_date_time(_required(payload, "end")),
            oldSubject=_optional_string(payload, "oldSubject", 200),
            newSubject=_optional_string(payload, "newSubject", 200),
            oldRooms=_references(payload, "oldRooms"),
            newRooms=_references(payload, "newRooms"),
            oldTeachers=_references(payload, "oldTeachers"),
            newTeachers=_references(payload, "newTeachers"),
            oldClasses=_references(payload, "oldClasses"),
            newClasses=_references(payload, "newClasses"),
            comment=_optional_string(payload, "comment", 2_000),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "oldSubject": self.oldSubject,
            "newSubject": self.newSubject,
            "oldRooms": [reference.to_payload() for reference in self.oldRooms],
            "newRooms": [reference.to_payload() for reference in self.newRooms],
            "oldTeachers": [reference.to_payload() for reference in self.oldTeachers],
            "newTeachers": [reference.to_payload() for reference in self.newTeachers],
            "oldClasses": [reference.to_payload() for reference in self.oldClasses],
            "newClasses": [reference.to_payload() for reference in self.newClasses],
            "comment": self.comment,
        }


def parse_upstream_substitutions(value: Any) -> list[UpstreamSubstitution]:
    if not isinstance(value, list) or len(value) > 10_000:
        raise SchemaValidationError("expected a bounded substitution list")
    return [UpstreamSubstitution.from_payload(item) for item in value]


@dataclass(frozen=True, slots=True)
class GateAnswer:
    answer: str

    @classmethod
    def from_payload(cls, value: Any) -> GateAnswer:
        payload = _object(value)
        if set(payload) != {"answer"}:
            raise SchemaValidationError("unexpected gate answer fields")
        answer = payload["answer"]
        if not isinstance(answer, str) or not 1 <= len(answer) <= 32:
            raise SchemaValidationError("invalid gate answer")
        if any(ord(character) < 32 for character in answer):
            raise SchemaValidationError("control characters are not allowed")
        return cls(answer=answer)


@dataclass(frozen=True, slots=True)
class FeedbackSubmission:
    message: str
    privacy_confirmed: bool

    @classmethod
    def from_payload(cls, value: Any) -> FeedbackSubmission:
        payload = _object(value)
        if set(payload) != {"message", "privacy_confirmed"}:
            raise SchemaValidationError("unexpected feedback fields")
        message = payload["message"]
        privacy_confirmed = payload["privacy_confirmed"]
        if not isinstance(message, str) or not 10 <= len(message) <= 1_500:
            raise SchemaValidationError("invalid feedback message")
        if not isinstance(privacy_confirmed, bool):
            raise SchemaValidationError("invalid privacy confirmation")
        return cls(message=message, privacy_confirmed=privacy_confirmed)
