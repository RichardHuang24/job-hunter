"""Applying a user's profile to their jobs: the role, the level and the
deal-breaker checks (app/matching/evaluate.py), stored on UserJob."""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, Profile, User, UserJob
from app.matching.evaluate import evaluate
from app.presets import get_catalog


class _NoProfile:
    seniority_levels: list[str] = []
    locations: list[str] = []
    work_arrangements: list[str] = []
    authorized_countries: list[str] = []
    open_to_sponsorship = False
    salary_min = None
    salary_currency = ""
    salary_period = "year"


class Matcher:
    """Everything needed to judge jobs for one user, worked out once."""

    def __init__(self, user: User):
        catalog = get_catalog()
        self.profile: Profile | _NoProfile = user.profile or _NoProfile()
        self.targets = list(user.targets)
        self.levels = catalog.levels_for(getattr(self.profile, "industry", ""))
        self.level_labels = {lv.key: lv.label for lv in catalog.levels}
        self.countries = catalog.countries

    def apply(self, user_job: UserJob, job: Job, now: dt.datetime) -> None:
        result = evaluate(job, self.profile, self.targets, self.levels, self.level_labels, self.countries)
        user_job.target_id = result.target.id if result.target is not None else None
        user_job.role = result.target.label if result.target is not None else ""
        user_job.level = result.level
        user_job.verdict = result.verdict
        user_job.checks = [asdict(check) for check in result.checks]
        user_job.updated_at = now


def rematch(db: Session, user: User) -> int:
    """Re-judge every job this user has, after their profile or roles change."""
    matcher = Matcher(user)
    now = dt.datetime.now(dt.UTC)
    rows = db.execute(select(UserJob, Job).join(Job, UserJob.job_id == Job.id).where(UserJob.user_id == user.id)).all()
    for user_job, job in rows:
        matcher.apply(user_job, job, now)
    return len(rows)
