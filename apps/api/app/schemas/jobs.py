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


class ScoreBrief(BaseModel):
    status: str  # queued, done, failed
    overall: int | None  # 0-100
    band: str  # "Strong fit"... (presets/scoring.toml)
    simulated: bool  # made by the simulated scorer, not Claude
    stale: bool  # the profile, roles or posting changed since


class DimensionRead(BaseModel):
    key: str
    label: str
    weight: int  # percent
    score: int
    reason: str


class EvidenceRead(BaseModel):
    requirement: str  # quoted from the posting
    verified: bool  # the quote was found in the posting
    detail: str = ""
    note: str = ""
    kind: str = ""  # required / nice_to_have, for gaps


class ScoreRead(ScoreBrief):
    advice: str
    provider: str  # anthropic, simulated
    model: str
    dimensions: list[DimensionRead]
    summary: str
    matched: list[EvidenceRead]
    missing: list[EvidenceRead]
    risks: list[str]
    unclear: list[str]
    error: str
    error_code: str  # limit, auth, rate_limited, refusal...
    cost_usd: float
    requested_at: UtcDatetime
    scored_at: UtcDatetime | None


class AiStatus(BaseModel):
    provider: str  # anthropic, simulated
    model: str
    effort: str
    auto_score: bool
    month: str  # 2026-10
    scores_used: int
    scores_limit: int
    queued: int
    cost_usd: float
    budget_usd: float


class UserJobRead(BaseModel):
    id: str
    state: str  # new, saved, hidden
    verdict: str  # match, flagged, filtered
    role: str  # the target role it counts as; "" for none
    level: Named
    checks: list[CheckRead]
    first_seen_at: UtcDatetime
    job: JobRead
    score: ScoreBrief | None


class UserJobDetail(UserJobRead):
    job: JobDetail
    score: ScoreRead | None


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
