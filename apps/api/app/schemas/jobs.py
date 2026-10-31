"""A user's jobs: the shared posting plus what they make of it."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.me import Named, UtcDatetime


class JobRead(BaseModel):
    id: str
    source: str
    source_label: str
    demo: bool  # from the built-in sample data
    url: str
    title: str
    company: str
    location: str
    country: str
    arrangement: str
    salary_min: int | None
    salary_max: int | None
    salary_currency: str
    salary_period: str
    posted_at: UtcDatetime | None


class JobDetail(JobRead):
    description: str


class CheckRead(BaseModel):
    key: str  # role, level, arrangement, location, permit, salary
    status: str  # pass, flag, fail, unknown
    detail: str


class UserJobRead(BaseModel):
    id: str
    state: str  # new, saved, hidden
    verdict: str  # match, flagged, filtered
    role: str  # the target role it counts as; "" for none
    level: Named
    checks: list[CheckRead]
    first_seen_at: UtcDatetime
    job: JobRead


class UserJobDetail(UserJobRead):
    job: JobDetail


class JobCounts(BaseModel):
    matches: int
    flagged: int
    filtered: int
    saved: int
    hidden: int


class JobList(BaseModel):
    items: list[UserJobRead]
    total: int  # in this view
    counts: JobCounts  # every view


class JobPatch(BaseModel):
    state: Literal["new", "saved", "hidden"]
