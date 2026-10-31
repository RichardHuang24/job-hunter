"""Database models.

Auth.js owns sign-in: `users`, `accounts`, `sessions` and `verification_token`
follow the schema its Postgres adapter (@auth/pg-adapter) reads and writes -
same table and column names, quoted camelCase included - with foreign keys
and unique indexes added. Alembic creates every table, Auth.js's too, so one
migration history describes the whole database.

Everything else belongs to a user and carries `user_id`.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, false, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


UtcDateTime = DateTime(timezone=True)


# --- Auth.js (@auth/pg-adapter) ---------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    email_verified: Mapped[dt.datetime | None] = mapped_column("emailVerified", UtcDateTime, nullable=True)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped["Profile | None"] = relationship(back_populates="user", cascade="all, delete-orphan")
    targets: Mapped[list["ProfileTarget"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="ProfileTarget.position"
    )
    searches: Mapped[list["SavedSearch"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="SavedSearch.created_at"
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("provider", "providerAccountId", name="uq_accounts_provider_account"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column("userId", ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(255))
    provider_account_id: Mapped[str] = mapped_column("providerAccountId", String(255))
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    id_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column("userId", ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires: Mapped[dt.datetime] = mapped_column(UtcDateTime)
    session_token: Mapped[str] = mapped_column("sessionToken", String(255), unique=True)


class VerificationToken(Base):
    __tablename__ = "verification_token"

    identifier: Mapped[str] = mapped_column(Text, primary_key=True)
    token: Mapped[str] = mapped_column(Text, primary_key=True)
    expires: Mapped[dt.datetime] = mapped_column(UtcDateTime)


# --- The product --------------------------------------------------------------------------


def _list_column() -> Mapped[list]:
    return mapped_column(JSON, default=list, server_default=text("'[]'"))


class Profile(Base):
    """Who a user is and what they're looking for. The deal-breakers here -
    locations, work arrangements, work permits, salary - become pass/fail
    checks on each job; the rest feeds matching and the CV."""

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    headline: Mapped[str] = mapped_column(String(255), default="")  # "Registered nurse", "Marketing manager"
    summary: Mapped[str] = mapped_column(Text, default="", server_default="")  # in their own words
    industry: Mapped[str] = mapped_column(String(64), default="")  # a preset key, presets/industries/
    market: Mapped[str] = mapped_column(String(64), default="")  # a preset key, presets/markets/
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seniority_levels: Mapped[list[str]] = _list_column()  # the levels wanted (presets/seniority.toml); [] = any
    skills: Mapped[list[str]] = _list_column()
    languages: Mapped[list[dict]] = _list_column()  # [{"name": "Spanish", "level": "professional"}]
    locations: Mapped[list[str]] = _list_column()  # places they'd work: "Manchester", "Remote (UK)"
    work_arrangements: Mapped[list[str]] = _list_column()  # onsite / hybrid / remote; [] = any
    authorized_countries: Mapped[list[str]] = _list_column()  # ISO codes where no visa is needed
    open_to_sponsorship: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(3), default="", server_default="")
    salary_period: Mapped[str] = mapped_column(String(8), default="year", server_default="year")
    onboarded_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="profile")


class ProfileTarget(Base):
    """A role the user is after: which job titles count as it (and which
    don't), and what to search for. Usually starts from an industry preset's
    role (presets/industries/), then the user edits it."""

    __tablename__ = "profile_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(80))
    titles: Mapped[list[str]] = _list_column()  # a job title containing one of these is this role
    exclude: Mapped[list[str]] = _list_column()  # ...unless it contains one of these
    search: Mapped[list[str]] = _list_column()  # what to type into job boards
    preset_role: Mapped[str] = mapped_column(String(130), default="", server_default="")  # "healthcare/registered-nurse"
    created_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="targets")


class Job(Base):
    """A posting, stored once however many people's searches find it. What
    each person makes of it is in UserJob."""

    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_jobs_source_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(32))  # app/sources key
    source_id: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    country: Mapped[str] = mapped_column(String(2), default="")  # ISO code; "" when not stated
    arrangement: Mapped[str] = mapped_column(String(8), default="")  # onsite / hybrid / remote / ""
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(3), default="")
    salary_period: Mapped[str] = mapped_column(String(8), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
    # Remote jobs: where candidates may live (ISO codes), or anywhere.
    countries: Mapped[list[str]] = _list_column()
    worldwide: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Taken down: past its expiry date, or the source says it has closed.
    # Closed and expired jobs leave every list except Saved and Hidden.
    expires_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
    closed_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
    checked_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)  # last asked the source
    # The same job listed by two sources: company, title and place, normalised.
    fingerprint: Mapped[str] = mapped_column(String(40), index=True)
    first_seen_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)

    def is_closed(self, now: dt.datetime) -> bool:
        if self.closed_at is not None:
            return True
        expires = self.expires_at
        if expires is not None and expires.tzinfo is None:  # SQLite hands back naive UTC
            expires = expires.replace(tzinfo=dt.UTC)
        return expires is not None and expires <= now


class SavedSearch(Base):
    """What to look for, and how often. The first one is made from the
    profile at the end of onboarding."""

    __tablename__ = "saved_searches"
    __table_args__ = (Index("ix_saved_searches_due", "daily", "next_run_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    terms: Mapped[list[str]] = _list_column()  # "staff nurse", "research nurse"
    locations: Mapped[list[str]] = _list_column()  # places; [] = anywhere in `countries`
    countries: Mapped[list[str]] = _list_column()  # ISO codes; [] = anywhere
    include_remote: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    sources: Mapped[list[str]] = _list_column()  # app/sources keys; [] = every enabled source
    daily: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    next_run_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
    last_run_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="searches")
    runs: Mapped[list["SearchRun"]] = relationship(
        back_populates="search", cascade="all, delete-orphan", order_by="SearchRun.created_at.desc()"
    )


RUN_STATUSES = ("queued", "running", "succeeded", "failed")


class SearchRun(Base):
    """One run of a saved search, done by the worker (app/search/runner.py)."""

    __tablename__ = "search_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    search_id: Mapped[str] = mapped_column(ForeignKey("saved_searches.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    trigger: Mapped[str] = mapped_column(String(16), default="manual")  # manual / schedule / onboarding
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    errors: Mapped[list[dict]] = mapped_column(JSON, default=list)  # [{"source": "demo", "message": "..."}]
    created_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    started_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)

    search: Mapped[SavedSearch] = relationship(back_populates="runs")


JOB_STATES = ("new", "saved", "hidden")
VERDICTS = ("match", "flagged", "filtered")


class UserJob(Base):
    """One person's view of a job: which of their roles it is, how it fares
    against their deal-breakers (app/matching/evaluate.py), and whether
    they've saved or hidden it."""

    __tablename__ = "user_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_jobs_user_job"),
        Index("ix_user_jobs_list", "user_id", "verdict", "state"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(8), default="new")
    target_id: Mapped[str | None] = mapped_column(ForeignKey("profile_targets.id", ondelete="SET NULL"), nullable=True)
    role: Mapped[str] = mapped_column(String(80), default="")  # the target's label when last checked
    level: Mapped[str] = mapped_column(String(16), default="")
    verdict: Mapped[str] = mapped_column(String(8), default="match")
    checks: Mapped[list[dict]] = mapped_column(JSON, default=list)
    first_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    first_seen_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)

    job: Mapped[Job] = relationship()
    score: Mapped["JobScore | None"] = relationship(back_populates="user_job", cascade="all, delete-orphan")


SCORE_STATUSES = ("queued", "done", "failed")


class JobScore(Base):
    """How well a job fits its user, scored by Claude or the simulator
    (app/scoring). One per UserJob; scoring again replaces it."""

    __tablename__ = "job_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    user_job_id: Mapped[str] = mapped_column(ForeignKey("user_jobs.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(8), default="queued")
    provider: Mapped[str] = mapped_column(String(16), default="")  # anthropic / simulated
    model: Mapped[str] = mapped_column(String(64), default="")
    overall: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100, weighted by the industry preset
    band: Mapped[str] = mapped_column(String(32), default="")  # presets/scoring.toml
    dimensions: Mapped[list[dict]] = mapped_column(JSON, default=list)  # [{key, label, weight, score, reason}]
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)  # summary, matched, missing, risks, unclear
    inputs_hash: Mapped[str] = mapped_column(String(32), default="")  # what was scored; differs once out of date
    error: Mapped[str] = mapped_column(Text, default="")
    error_code: Mapped[str] = mapped_column(String(16), default="")
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    requested_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    scored_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)

    user_job: Mapped[UserJob] = relationship(back_populates="score")


class AiUsage(Base):
    """Every AI call, for the monthly limits and the bill."""

    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_user_month", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16), default="score")
    provider: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)


APPLICATION_STATUSES: tuple[tuple[str, str], ...] = (
    ("planned", "To apply"), ("applied", "Applied"), ("interviewing", "Interviewing"), ("offer", "Offer"),
    ("accepted", "Accepted"), ("rejected", "Rejected"), ("withdrawn", "Withdrawn"), ("no_response", "No response"),
)
ACTIVE_STATUSES = ("planned", "applied", "interviewing", "offer")  # the rest are closed


class Application(Base):
    """A job someone has applied for, or means to - from their jobs, or added
    by hand. The job's details are copied in, so the application keeps them
    if the posting closes; `events` is its history of statuses."""

    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_job_id", name="uq_applications_user_job"),
        Index("ix_applications_user", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_job_id: Mapped[str | None] = mapped_column(ForeignKey("user_jobs.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="applied")
    applied_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    next_step: Mapped[str] = mapped_column(String(200), default="")  # "Phone screen with the ward manager"
    next_step_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)

    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", cascade="all, delete-orphan",
        order_by="(ApplicationEvent.at, ApplicationEvent.id)")


class ApplicationEvent(Base):
    """A step in an application's history: made, or moved to a status."""

    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # created, status
    status: Mapped[str] = mapped_column(String(16))
    at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)

    application: Mapped[Application] = relationship(back_populates="events")


class Cv(Base):
    """A person's CV as structured data (app/cv/schema.py). One per person;
    until they save it, the CV page starts from their profile."""

    __tablename__ = "cvs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)


class Document(Base):
    """A file made for someone - a CV PDF, built by the worker and kept in
    storage (app/storage.py) under `storage_key`."""

    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_user", "user_id", "requested_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16), default="cv")
    status: Mapped[str] = mapped_column(String(8), default="queued")  # queued, done, failed
    filename: Mapped[str] = mapped_column(String(200), default="")  # what it downloads as
    storage_key: Mapped[str] = mapped_column(String(255), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    requested_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)


class BillingEvent(Base):
    """Every Stripe webhook event received, once (Stripe retries), so billing
    can be rebuilt from them (app/billing.py)."""

    __tablename__ = "billing_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # Stripe's event id, evt_...
    type: Mapped[str] = mapped_column(String(100))
    livemode: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    received_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)


TASK_STATUSES = ("queued", "running", "succeeded", "failed")


class Task(Base):
    """One unit of background work for the worker (app/worker.py): a search,
    an AI match batch, a CV build. Postgres is the queue - workers claim rows
    with SELECT ... FOR UPDATE SKIP LOCKED (app/tasks/queue.py)."""

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_claim", "status", "run_after"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    locked_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
    locked_by: Mapped[str] = mapped_column(String(128), default="")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(UtcDateTime, default=_utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime, nullable=True)
