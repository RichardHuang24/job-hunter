"""The admin page's numbers (GET /admin/overview): people, AI costs per
person, how each job source is doing, and the task queue. Read-only, and
for the addresses in ADMIN_EMAILS only (app/auth.py)."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import AiUsage, Document, Profile, SearchRun, Task, User
from app.scoring.service import month_start
from app.sources import SOURCES, enabled_sources

SOURCE_WINDOW = dt.timedelta(days=7)
QUEUE_WINDOW = dt.timedelta(hours=24)
TOP_USERS = 50


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    if value is not None and value.tzinfo is None:  # SQLite hands back naive UTC
        return value.replace(tzinfo=dt.UTC)
    return value


def _people(db: Session, now: dt.datetime) -> dict:
    return {
        "total": db.scalar(select(func.count()).select_from(User)) or 0,
        "set_up": db.scalar(select(func.count()).select_from(Profile).where(Profile.onboarded_at.is_not(None))) or 0,
        "new_7_days": db.scalar(select(func.count()).select_from(User).where(User.created_at >= now - dt.timedelta(days=7))) or 0,
    }


def _ai(db: Session, now: dt.datetime, settings: Settings) -> dict:
    start = month_start(now)
    rows = db.execute(
        select(AiUsage.user_id, User.email, func.count(), func.sum(AiUsage.cost_usd),
               func.sum(AiUsage.input_tokens + AiUsage.cache_read_tokens + AiUsage.cache_write_tokens),
               func.sum(AiUsage.output_tokens))
        .join(User, User.id == AiUsage.user_id).where(AiUsage.created_at >= start)
        .group_by(AiUsage.user_id, User.email).order_by(func.sum(AiUsage.cost_usd).desc(), AiUsage.user_id)
    ).all()
    by_model = db.execute(select(AiUsage.model, func.count(), func.sum(AiUsage.cost_usd)).where(AiUsage.created_at >= start)
                          .group_by(AiUsage.model).order_by(func.sum(AiUsage.cost_usd).desc())).all()
    budget = settings.ai_budget_usd_per_month
    return {
        "month": start.strftime("%Y-%m"),
        "scores": sum(r[2] for r in rows),
        "cost_usd": round(sum(r[3] or 0 for r in rows), 4),
        "by_model": [{"model": m, "scores": n, "cost_usd": round(c or 0, 4)} for m, n, c in by_model],
        "by_user": [{
            "user_id": uid, "email": email or "", "scores": n, "cost_usd": round(cost or 0, 4),
            "input_tokens": int(tin or 0), "output_tokens": int(tout or 0),
            "budget_used": round((cost or 0) / budget, 3) if budget else None,
        } for uid, email, n, cost, tin, tout in rows[:TOP_USERS]],
        "people_scoring": len(rows),
        "scores_per_person": settings.ai_scores_per_month, "budget_per_person_usd": budget,
    }


def _sources(db: Session, now: dt.datetime) -> list[dict]:
    """Each source over the last 7 days: in how many runs it was asked, how
    many of those failed, and its latest error."""
    stats: dict[str, dict] = defaultdict(lambda: {"runs": 0, "failed": 0, "postings": 0, "last_error": "",
                                                   "last_error_at": None, "last_ok_at": None})
    runs = db.execute(select(SearchRun.counts, SearchRun.errors, SearchRun.finished_at)
                      .where(SearchRun.status == "succeeded", SearchRun.finished_at >= now - SOURCE_WINDOW)
                      .order_by(SearchRun.finished_at)).all()
    for counts, errors, finished in runs:
        asked = (counts or {}).get("sources") or {}
        failed = {e.get("source") for e in errors or []}
        for key, s in asked.items():
            entry = stats[key]
            entry["runs"] += 1
            entry["postings"] += int(s.get("postings", 0))
            if key in failed or s.get("error"):
                entry["failed"] += 1
                entry["last_error"] = s.get("error") or next((e["message"] for e in errors if e.get("source") == key), "")
                entry["last_error_at"] = _aware(finished)
            else:
                entry["last_ok_at"] = _aware(finished)
    rechecks = db.scalars(select(Task).where(Task.kind == "recheck", Task.status == "succeeded")
                          .order_by(Task.finished_at.desc()).limit(1)).first()
    last_recheck = (rechecks.result or {}) if rechecks else {}
    keys = [s.key for s in enabled_sources()] + [k for k in stats if k not in {s.key for s in enabled_sources()}]
    out = []
    for key in keys:
        entry = stats[key] if key in stats else {"runs": 0, "failed": 0, "postings": 0, "last_error": "",
                                                  "last_error_at": None, "last_ok_at": None}
        source = SOURCES.get(key)
        recheck = last_recheck.get(key) if isinstance(last_recheck.get(key), dict) else None
        out.append({
            "key": key, "label": source.label if source else key, "enabled": key in {s.key for s in enabled_sources()},
            **entry, "error_rate": round(entry["failed"] / entry["runs"], 3) if entry["runs"] else None,
            "last_recheck": recheck,
        })
    return out


def _queue(db: Session, now: dt.datetime, settings: Settings) -> dict:
    since = now - QUEUE_WINDOW
    kinds: dict[str, dict] = defaultdict(lambda: {"queued": 0, "running": 0, "succeeded_24h": 0, "failed_24h": 0})
    for kind, status, n in db.execute(select(Task.kind, Task.status, func.count())
                                      .where(Task.status.in_(("queued", "running"))).group_by(Task.kind, Task.status)):
        kinds[kind][status] = n
    for kind, status, n in db.execute(select(Task.kind, Task.status, func.count())
                                      .where(Task.status.in_(("succeeded", "failed")), Task.finished_at >= since)
                                      .group_by(Task.kind, Task.status)):
        kinds[kind][f"{status}_24h"] = n
    oldest = _aware(db.scalar(select(func.min(Task.run_after)).where(Task.status == "queued", Task.run_after <= now)))
    stuck = db.scalar(select(func.count()).select_from(Task).where(
        Task.status == "running", Task.locked_at < now - dt.timedelta(seconds=settings.task_lease_seconds))) or 0
    failures = db.scalars(select(Task).where(Task.status == "failed").order_by(Task.finished_at.desc()).limit(10)).all()
    return {
        "by_kind": [{"kind": kind, **counts} for kind, counts in sorted(kinds.items())],
        "waiting_seconds": round((now - oldest).total_seconds()) if oldest else 0,
        "stuck": stuck,
        "recent_failures": [{"kind": t.kind, "error": (t.error or "")[:300], "at": _aware(t.finished_at),
                             "user_id": t.user_id, "attempts": t.attempts} for t in failures],
    }


def _pdfs(db: Session, now: dt.datetime) -> dict:
    rows = dict(db.execute(select(Document.status, func.count()).where(Document.requested_at >= now - SOURCE_WINDOW)
                           .group_by(Document.status)).all())
    return {"done_7_days": rows.get("done", 0), "failed_7_days": rows.get("failed", 0), "queued": rows.get("queued", 0)}


def overview(db: Session, now: dt.datetime | None = None, settings: Settings | None = None) -> dict:
    now = now or dt.datetime.now(dt.UTC)
    settings = settings or get_settings()
    return {
        "generated_at": now, "people": _people(db, now), "ai": _ai(db, now, settings),
        "sources": _sources(db, now), "queue": _queue(db, now, settings), "cv_pdfs": _pdfs(db, now),
    }
