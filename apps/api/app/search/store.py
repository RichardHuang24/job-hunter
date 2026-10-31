"""The shared job store: one row per posting per source, updated in place."""

from __future__ import annotations

import datetime as dt
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job
from app.matching.titles import normalize
from app.sources.base import Posting


def fingerprint(company: str, title: str, location: str) -> str:
    """The same job listed by two sources gets the same fingerprint."""
    key = "|".join(normalize(part) for part in (company, title, location))
    return hashlib.sha1(key.encode()).hexdigest()


def _clip(text: str, length: int) -> str:
    return (text or "").strip()[:length]


def upsert(db: Session, source: str, posting: Posting, now: dt.datetime) -> Job:
    job = db.scalar(select(Job).where(Job.source == source, Job.source_id == posting.source_id))
    if job is None:
        job = Job(source=source, source_id=_clip(posting.source_id, 200), first_seen_at=now)
        db.add(job)
    job.url = posting.url
    job.title = _clip(posting.title, 300)
    job.company = _clip(posting.company, 200)
    job.location = _clip(posting.location, 200)
    job.country = posting.country if len(posting.country) == 2 else ""
    job.arrangement = posting.arrangement if posting.arrangement in ("onsite", "hybrid", "remote") else ""
    job.salary_min, job.salary_max = posting.salary_min, posting.salary_max
    job.salary_currency = _clip(posting.salary_currency, 3).upper()
    job.salary_period = posting.salary_period if posting.salary_period in ("year", "month", "day", "hour") else ""
    job.description = _clip(posting.description, 20_000)
    job.posted_at = posting.posted_at
    job.fingerprint = fingerprint(posting.company, posting.title, posting.location)
    job.last_seen_at = now
    return job
