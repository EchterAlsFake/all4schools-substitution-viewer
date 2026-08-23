from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NamedReference(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    name: str | None = Field(default=None, max_length=200)


class UpstreamSubstitution(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    type: int
    start: datetime
    end: datetime
    oldSubject: str | None = Field(default=None, max_length=200)
    newSubject: str | None = Field(default=None, max_length=200)
    oldRooms: list[NamedReference] = Field(default_factory=list, max_length=32)
    newRooms: list[NamedReference] = Field(default_factory=list, max_length=32)
    oldTeachers: list[NamedReference] = Field(default_factory=list, max_length=32)
    newTeachers: list[NamedReference] = Field(default_factory=list, max_length=32)
    oldClasses: list[NamedReference] = Field(default_factory=list, max_length=32)
    newClasses: list[NamedReference] = Field(default_factory=list, max_length=32)
    comment: str | None = Field(default=None, max_length=2_000)


class GateAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=32)

    @field_validator("answer")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("control characters are not allowed")
        return value


class FeedbackSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=10, max_length=1_500)
    privacy_confirmed: bool

