"""Applications: what's sent, and what comes back."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import APPLICATION_STATUSES
from app.schemas.me import Text, UtcDatetime

STATUS_KEYS = tuple(key for key, _ in APPLICATION_STATUSES)


def _status(value: str) -> str:
    if value not in STATUS_KEYS:
        raise ValueError(f"status must be one of {', '.join(STATUS_KEYS)}")
    return value


def _link(value: str) -> str:
    value = value.strip()
    if value and not value.startswith(("https://", "http://")):
        raise ValueError("a link must start with http:// or https://")
    return value


Status = Annotated[str, AfterValidator(_status)]
Link = Annotated[str, AfterValidator(_link), Field(max_length=2000)]


class ApplicationCreate(BaseModel):
    """From one of your jobs (user_job_id), or by hand (title at least)."""

    user_job_id: str | None = None
    title: Annotated[Text, Field(max_length=300)] = ""
    company: Annotated[Text, Field(max_length=200)] = ""
    location: Annotated[Text, Field(max_length=200)] = ""
    url: Link = ""
    status: Status = "applied"
    applied_on: dt.date | None = None
    notes: Annotated[str, Field(max_length=5000)] = ""

    @model_validator(mode="after")
    def _something_to_track(self) -> ApplicationCreate:
        if not self.user_job_id and not self.title:
            raise ValueError("give the job's title, or the job it's for")
        return self


class ApplicationPatch(BaseModel):
    """Only the fields sent change; null clears a date."""

    title: Annotated[Text, Field(min_length=1, max_length=300)] | None = None
    company: Annotated[Text, Field(max_length=200)] | None = None
    location: Annotated[Text, Field(max_length=200)] | None = None
    url: Link | None = None
    status: Status | None = None
    applied_on: dt.date | None = None
    next_step: Annotated[Text, Field(max_length=200)] | None = None
    next_step_on: dt.date | None = None
    notes: Annotated[str, Field(max_length=5000)] | None = None

    @field_validator("title", "company", "location", "url", "status", "next_step", "notes")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("can't be empty here - send a value or leave it out")
        return value


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str  # created, status
    status: str
    at: UtcDatetime


class ApplicationRead(BaseModel):
    id: str
    user_job_id: str | None  # the job it came from; None if added by hand
    title: str
    company: str
    location: str
    url: str
    status: str
    applied_on: dt.date | None
    next_step: str
    next_step_on: dt.date | None
    notes: str
    job_closed: bool  # the posting it came from has closed or expired
    created_at: UtcDatetime
    updated_at: UtcDatetime


class ApplicationDetail(ApplicationRead):
    events: list[EventRead]


class ApplicationCounts(BaseModel):
    active: int
    closed: int
    by_status: dict[str, int]


class ApplicationList(BaseModel):
    items: list[ApplicationRead]
    total: int
    counts: ApplicationCounts


class TrackedRead(BaseModel):
    """On a job: the application it has, if any."""

    id: str
    status: str
