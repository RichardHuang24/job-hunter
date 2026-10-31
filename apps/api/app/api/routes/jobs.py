"""The signed-in user's jobs, in views: matches, flagged, filtered out,
saved and hidden."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db.models import Job, User, UserJob
from app.db.session import get_db
from app.presets import get_catalog
from app.schemas.jobs import JobList, JobPatch, UserJobDetail, UserJobRead
from app.sources import SOURCES

router = APIRouter(prefix="/jobs", tags=["jobs"])

View = Literal["matches", "flagged", "filtered", "saved", "hidden"]
VERDICT = {"matches": "match", "flagged": "flagged", "filtered": "filtered"}


def _job(job: Job, detail: bool = False) -> dict:
    source = SOURCES.get(job.source)
    out = {
        "id": job.id, "source": job.source, "source_label": source.label if source else job.source,
        "demo": bool(source and source.demo), "url": job.url, "title": job.title, "company": job.company,
        "location": job.location, "country": job.country, "arrangement": job.arrangement,
        "salary_min": job.salary_min, "salary_max": job.salary_max, "salary_currency": job.salary_currency,
        "salary_period": job.salary_period, "posted_at": job.posted_at,
    }
    if detail:
        out["description"] = job.description
    return out


def _read(user_job: UserJob, job: Job, labels: dict[str, str], detail: bool = False) -> dict:
    return {
        "id": user_job.id, "state": user_job.state, "verdict": user_job.verdict, "role": user_job.role,
        "level": {"key": user_job.level, "label": labels.get(user_job.level, user_job.level)},
        "checks": user_job.checks, "first_seen_at": user_job.first_seen_at, "job": _job(job, detail),
    }


def _labels() -> dict[str, str]:
    return {lv.key: lv.label for lv in get_catalog().levels}


@router.get("", response_model=JobList)
def list_jobs(view: View = "matches", q: str = Query("", max_length=100), limit: int = 50, offset: int = 0,
              user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    mine = select(UserJob, Job).join(Job, UserJob.job_id == Job.id).where(UserJob.user_id == user.id)
    if view in VERDICT:
        mine = mine.where(UserJob.verdict == VERDICT[view], UserJob.state != "hidden")
    else:
        mine = mine.where(UserJob.state == ("hidden" if view == "hidden" else "saved"))
    if q.strip():
        like = f"%{q.strip()}%"
        mine = mine.where(or_(Job.title.ilike(like), Job.company.ilike(like), Job.location.ilike(like)))
    total = db.scalar(select(func.count()).select_from(mine.subquery()))
    rows = db.execute(mine.order_by(UserJob.first_seen_at.desc(), Job.posted_at.desc().nulls_last(), Job.id)
                      .limit(min(max(limit, 1), 200)).offset(max(offset, 0))).all()

    grouped = db.execute(select(UserJob.verdict, UserJob.state, func.count()).where(UserJob.user_id == user.id)
                         .group_by(UserJob.verdict, UserJob.state)).all()
    counts = {"matches": 0, "flagged": 0, "filtered": 0, "saved": 0, "hidden": 0}
    for verdict, state, n in grouped:
        if state == "hidden":
            counts["hidden"] += n
            continue
        if state == "saved":
            counts["saved"] += n
        counts[{"match": "matches", "flagged": "flagged", "filtered": "filtered"}[verdict]] += n
    labels = _labels()
    return {"items": [_read(uj, job, labels) for uj, job in rows], "total": total, "counts": counts}


def _mine(db: Session, user: User, user_job_id: str) -> tuple[UserJob, Job]:
    user_job = db.get(UserJob, user_job_id)
    if user_job is None or user_job.user_id != user.id:
        raise HTTPException(status_code=404, detail="No such job.")
    return user_job, db.get(Job, user_job.job_id)


@router.get("/{user_job_id}", response_model=UserJobDetail)
def get_job(user_job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    user_job, job = _mine(db, user, user_job_id)
    return _read(user_job, job, _labels(), detail=True)


@router.patch("/{user_job_id}", response_model=UserJobRead)
def patch_job(user_job_id: str, payload: JobPatch, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Save, hide, or put back (state "new")."""
    user_job, job = _mine(db, user, user_job_id)
    user_job.state = payload.state
    user_job.updated_at = dt.datetime.now(dt.UTC)
    db.commit()
    return _read(user_job, job, _labels())
