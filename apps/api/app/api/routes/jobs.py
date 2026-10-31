"""The signed-in user's jobs, in views: matches, flagged, filtered out,
saved and hidden. Jobs that have closed or expired leave the first three
(the sources' terms say to take them down); Saved and Hidden keep them,
marked closed, without the posting."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db.models import Job, JobScore, User, UserJob
from app.db.session import get_db
from app.presets import get_catalog
from app.schemas.jobs import JobList, JobPatch, ScoreRead, UserJobDetail, UserJobRead
from app.scoring import service as scoring
from app.sources import SOURCES

router = APIRouter(prefix="/jobs", tags=["jobs"])

View = Literal["matches", "flagged", "filtered", "saved", "hidden"]
VERDICT = {"matches": "match", "flagged": "flagged", "filtered": "filtered"}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def is_open(now: dt.datetime) -> ColumnElement[bool]:
    return and_(Job.closed_at.is_(None), or_(Job.expires_at.is_(None), Job.expires_at > now))


def _job(job: Job, detail: bool = False) -> dict:
    source = SOURCES.get(job.source)
    closed = job.is_closed(_now())
    out = {
        "id": job.id, "source": job.source, "source_label": source.label if source else job.source,
        "source_url": source.homepage if source else "", "demo": bool(source and source.demo), "closed": closed,
        "url": job.url, "title": job.title, "company": job.company,
        "location": job.location, "country": job.country, "arrangement": job.arrangement,
        "salary_min": job.salary_min, "salary_max": job.salary_max, "salary_currency": job.salary_currency,
        "salary_period": job.salary_period, "posted_at": job.posted_at,
    }
    if detail:
        out["description"] = "" if closed else job.description
    return out


def _read(user_job: UserJob, job: Job, labels: dict[str, str], context: scoring.Context, detail: bool = False) -> dict:
    score = user_job.score
    digest = context.request(user_job, job)[1] if score is not None else None
    return {
        "id": user_job.id, "state": user_job.state, "verdict": user_job.verdict, "role": user_job.role,
        "level": {"key": user_job.level, "label": labels.get(user_job.level, user_job.level)},
        "checks": user_job.checks, "first_seen_at": user_job.first_seen_at, "job": _job(job, detail),
        "score": (scoring.full if detail else scoring.brief)(score, digest),
    }


def _labels() -> dict[str, str]:
    return {lv.key: lv.label for lv in get_catalog().levels}


@router.get("", response_model=JobList)
def list_jobs(view: View = "matches", q: str = Query("", max_length=100), sort: Literal["recent", "fit"] = "recent",
              limit: int = 50, offset: int = 0, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """sort=fit puts the best AI scores first; jobs not scored yet come last."""
    now = _now()
    mine = (select(UserJob, Job).join(Job, UserJob.job_id == Job.id)
            .outerjoin(JobScore, JobScore.user_job_id == UserJob.id).where(UserJob.user_id == user.id))
    if view in VERDICT:
        mine = mine.where(UserJob.verdict == VERDICT[view], UserJob.state != "hidden", is_open(now))
    else:
        mine = mine.where(UserJob.state == ("hidden" if view == "hidden" else "saved"))
    if q.strip():
        like = f"%{q.strip()}%"
        mine = mine.where(or_(Job.title.ilike(like), Job.company.ilike(like), Job.location.ilike(like)))
    total = db.scalar(select(func.count()).select_from(mine.subquery()))
    order = [UserJob.first_seen_at.desc(), Job.posted_at.desc().nulls_last(), Job.id]
    if sort == "fit":
        order.insert(0, JobScore.overall.desc().nulls_last())
    rows = db.execute(mine.order_by(*order).limit(min(max(limit, 1), 200)).offset(max(offset, 0))).all()

    counts = {"matches": 0, "flagged": 0, "filtered": 0, "saved": 0, "hidden": 0}
    by_verdict = db.execute(select(UserJob.verdict, func.count()).join(Job, UserJob.job_id == Job.id)
                            .where(UserJob.user_id == user.id, UserJob.state != "hidden", is_open(now))
                            .group_by(UserJob.verdict)).all()
    for verdict, n in by_verdict:
        counts[{"match": "matches", "flagged": "flagged", "filtered": "filtered"}[verdict]] += n
    by_state = db.execute(select(UserJob.state, func.count()).where(UserJob.user_id == user.id, UserJob.state != "new")
                          .group_by(UserJob.state)).all()
    for state, n in by_state:
        counts[state] += n
    labels, context = _labels(), scoring.Context.of(user)
    return {"items": [_read(uj, job, labels, context) for uj, job in rows], "total": total, "counts": counts}


def _mine(db: Session, user: User, user_job_id: str) -> tuple[UserJob, Job]:
    user_job = db.get(UserJob, user_job_id)
    if user_job is None or user_job.user_id != user.id:
        raise HTTPException(status_code=404, detail="No such job.")
    return user_job, db.get(Job, user_job.job_id)


@router.get("/{user_job_id}", response_model=UserJobDetail)
def get_job(user_job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    user_job, job = _mine(db, user, user_job_id)
    return _read(user_job, job, _labels(), scoring.Context.of(user), detail=True)


@router.patch("/{user_job_id}", response_model=UserJobRead)
def patch_job(user_job_id: str, payload: JobPatch, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Save, hide, or put back (state "new")."""
    user_job, job = _mine(db, user, user_job_id)
    user_job.state = payload.state
    user_job.updated_at = dt.datetime.now(dt.UTC)
    db.commit()
    return _read(user_job, job, _labels(), scoring.Context.of(user))


@router.post("/{user_job_id}/score", response_model=ScoreRead, status_code=202)
def score_job(user_job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Queues an AI score (or a fresh one) for this job; the worker makes it.
    Poll GET /jobs/{id} until score.status is no longer "queued"."""
    user_job, job = _mine(db, user, user_job_id)
    if job.is_closed(_now()):
        raise HTTPException(status_code=410, detail="This job has closed.")
    if user_job.score is not None and user_job.score.status == "queued":
        raise HTTPException(status_code=409, detail="This job is already being scored.")
    try:
        scoring.queue(db, user, [user_job], asked=True)
    except scoring.LimitReached as exc:
        raise HTTPException(status_code=429, detail="This month's AI scoring allowance is used up.") from exc
    db.commit()
    db.refresh(user_job)
    return scoring.full(user_job.score, scoring.Context.of(user).request(user_job, job)[1])
