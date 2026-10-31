"""Queueing scores, doing them on the worker, the monthly limits, and how a
score reads in the API.

Scores are made by the worker ("score" task), a batch at a time. Each user
has a monthly allowance - AI_SCORES_PER_MONTH scores and
AI_BUDGET_USD_PER_MONTH dollars - checked when scores are queued and again
before each call. Every call is recorded in ai_usage.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import AiUsage, Job, JobScore, User, UserJob
from app.presets import get_catalog
from app.scoring.prompt import (
    SYSTEM_INSTRUCTIONS,
    Dimension,
    band_for,
    candidate_block,
    inputs_hash,
    user_message,
    weighted_overall,
)
from app.scoring.providers import NotConfigured, ScoreRequest, ScoreResult, ScoringError, get_scorer
from app.tasks import queue as tasks

log = logging.getLogger("job_hunter.scoring")

AUTO_VERDICTS = ("match", "flagged")  # filtered-out jobs aren't scored unless asked


class LimitReached(Exception):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def month_start(now: dt.datetime) -> dt.datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def usage_this_month(db: Session, user_id: int, now: dt.datetime | None = None) -> tuple[int, float]:
    """(scores made, dollars spent) since the start of the month."""
    count, cost = db.execute(
        select(func.count(), func.coalesce(func.sum(AiUsage.cost_usd), 0.0))
        .where(AiUsage.user_id == user_id, AiUsage.created_at >= month_start(now or _now()))
    ).one()
    return int(count), float(cost)


def queued_count(db: Session, user_id: int) -> int:
    return db.scalar(select(func.count()).select_from(JobScore).where(JobScore.user_id == user_id, JobScore.status == "queued"))


def allowance(db: Session, user_id: int, settings: Settings | None = None) -> int:
    """How many more scores can be queued this month."""
    settings = settings or get_settings()
    used, spent = usage_this_month(db, user_id)
    if spent >= settings.ai_budget_usd_per_month:
        return 0
    return max(0, settings.ai_scores_per_month - used - queued_count(db, user_id))


@dataclass
class Context:
    """Everything about one user that every score of theirs shares."""

    system: str
    weights: dict[str, int]
    dimensions: list[Dimension]
    skills: tuple[str, ...]
    field_skills: tuple[str, ...]
    wanted_levels: tuple[str, ...]

    @classmethod
    def of(cls, user: User) -> Context:
        catalog = get_catalog()
        profile = user.profile
        industry = catalog.industries.get(profile.industry) if profile else None
        market = catalog.markets.get(profile.market) if profile else None
        weights = dict(industry.scoring) if industry else {key: 25 for key in catalog.dimensions}
        dimensions = [Dimension(d.key, d.label, d.description, weights.get(d.key, 0)) for d in catalog.dimensions.values()]
        block = candidate_block(profile, list(user.targets), industry=industry.label if industry else "",
                                market=market.label if market else "", levels={lv.key: lv.label for lv in catalog.levels},
                                dimensions=dimensions)
        return cls(
            system=f"{SYSTEM_INSTRUCTIONS}\n\n{block}", weights=weights, dimensions=dimensions,
            skills=tuple(profile.skills) if profile else (), field_skills=industry.skills if industry else (),
            wanted_levels=tuple(profile.seniority_levels) if profile else (),
        )

    def request(self, user_job: UserJob, job: Job) -> tuple[ScoreRequest, str]:
        checks = list(user_job.checks or [])
        message = user_message(title=job.title, company=job.company, location=job.location, checks=checks,
                               description=job.description)
        arrangement = next((c["status"] for c in checks if c["key"] == "arrangement"), "unknown")
        request = ScoreRequest(
            system=self.system, message=message, posting=f"{job.title}\n{job.description}", skills=self.skills,
            role=user_job.role, level_wanted=(user_job.level in self.wanted_levels) if self.wanted_levels else None,
            arrangement_fits={"pass": True, "fail": False}.get(arrangement), field_skills=self.field_skills,
            flags=tuple(c["detail"] for c in checks if c["status"] == "flag"),
            unknowns=tuple(c["detail"] for c in checks if c["status"] == "unknown"),
        )
        return request, inputs_hash(self.system, message)


def queue(db: Session, user: User, user_jobs: Sequence[UserJob], *, asked: bool) -> list[JobScore]:
    """Queues scores for these jobs (skipping any already queued) and a worker
    task to make them. `asked`: the user asked - raise LimitReached rather
    than quietly queueing fewer."""
    room = allowance(db, user.id)
    if asked and room <= 0:
        raise LimitReached()
    now = _now()
    queued = []
    for user_job in user_jobs:
        if len(queued) >= room:
            break
        score = user_job.score
        if score is not None and score.status == "queued":
            continue
        if score is None:
            score = JobScore(user_id=user.id, user_job_id=user_job.id)
            db.add(score)
            user_job.score = score
        score.status, score.error, score.error_code, score.requested_at = "queued", "", "", now
        queued.append(score)
    if queued:
        db.flush()
        tasks.enqueue(db, "score", {"score_ids": [s.id for s in queued]}, user_id=user.id, max_attempts=1)
    return queued


def queue_after_run(db: Session, user: User, new_jobs: Iterable[UserJob]) -> int:
    """After a search: score the new matches and flagged jobs, within the allowance."""
    if not get_settings().ai_auto_score:
        return 0
    wanted = [uj for uj in new_jobs if uj.verdict in AUTO_VERDICTS and uj.state != "hidden"]
    order = {"match": 0, "flagged": 1}
    wanted.sort(key=lambda uj: order[uj.verdict])
    return len(queue(db, user, wanted, asked=False))


def _fail(score: JobScore, code: str, message: str) -> None:
    score.status, score.error_code, score.error = "failed", code, message[:500]


def _store(db: Session, score: JobScore, result: ScoreResult, digest: str, context: Context) -> None:
    analysis = result.analysis
    overall = weighted_overall(analysis, context.weights)
    score.status, score.provider, score.model = "done", result.provider, result.model
    score.overall, score.band = overall, band_for(overall, get_catalog().bands).label
    score.dimensions = [{"key": d.key, "label": d.label, "weight": d.weight, **getattr(analysis.scores, d.key).model_dump()}
                        for d in context.dimensions]
    score.analysis = {"summary": analysis.summary, "matched": [m.model_dump() for m in analysis.matched],
                      "missing": [m.model_dump() for m in analysis.missing], "risks": analysis.risks,
                      "unclear": analysis.unclear}
    score.inputs_hash, score.cost_usd, score.scored_at = digest, result.cost_usd, _now()
    score.error, score.error_code = "", ""
    db.add(AiUsage(user_id=score.user_id, kind="score", provider=result.provider, model=result.model,
                   input_tokens=result.usage.input_tokens, output_tokens=result.usage.output_tokens,
                   cache_read_tokens=result.usage.cache_read_tokens, cache_write_tokens=result.usage.cache_write_tokens,
                   cost_usd=result.cost_usd, created_at=_now()))


def run_task(db: Session, score_ids: Sequence[str], settings: Settings | None = None) -> dict:
    """The worker's "score" task: scores one batch, committing after each."""
    settings = settings or get_settings()
    scores = [s for s in (db.get(JobScore, i) for i in score_ids) if s is not None and s.status == "queued"]
    done = failed = 0
    try:
        scorer = get_scorer(settings)
    except NotConfigured as exc:
        for score in scores:
            _fail(score, "config", str(exc))
        db.commit()
        return {"done": 0, "failed": len(scores)}
    contexts: dict[int, Context] = {}
    for index, score in enumerate(scores):
        used, spent = usage_this_month(db, score.user_id)
        if used >= settings.ai_scores_per_month or spent >= settings.ai_budget_usd_per_month:
            _fail(score, "limit", "This month's AI scoring allowance is used up.")
            failed += 1
            db.commit()
            continue
        user_job = score.user_job
        if score.user_id not in contexts:
            contexts[score.user_id] = Context.of(db.get(User, score.user_id))
        context = contexts[score.user_id]
        request, digest = context.request(user_job, user_job.job)
        try:
            result = scorer.score(request)
        except ScoringError as exc:
            _fail(score, exc.code, str(exc))
            failed += 1
            if exc.stop:  # the rest would fail the same way
                for rest in scores[index + 1:]:
                    _fail(rest, exc.code, str(exc))
                    failed += 1
                db.commit()
                break
            db.commit()
            continue
        _store(db, score, result, digest, context)
        done += 1
        db.commit()
    log.info("Scored %d job(s), %d failed", done, failed)
    return {"done": done, "failed": failed}


# --- reading ----------------------------------------------------------------------------


def brief(score: JobScore | None, digest: str | None) -> dict | None:
    if score is None:
        return None
    return {"status": score.status, "overall": score.overall, "band": score.band,
            "simulated": score.provider == "simulated",
            "stale": score.status == "done" and digest is not None and digest != score.inputs_hash}


def full(score: JobScore | None, digest: str | None) -> dict | None:
    if score is None:
        return None
    advice = next((b.advice for b in get_catalog().bands if b.label == score.band), "")
    return {**brief(score, digest), "advice": advice, "provider": score.provider, "model": score.model,
            "dimensions": score.dimensions, "summary": score.analysis.get("summary", ""),
            "matched": score.analysis.get("matched", []), "missing": score.analysis.get("missing", []),
            "risks": score.analysis.get("risks", []), "unclear": score.analysis.get("unclear", []),
            "error": score.error, "error_code": score.error_code, "cost_usd": score.cost_usd,
            "requested_at": score.requested_at, "scored_at": score.scored_at}
