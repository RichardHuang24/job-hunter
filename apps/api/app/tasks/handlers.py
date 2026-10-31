"""What the worker can do: task kind -> handler. Each handler gets the
session and the task, and returns the task's result (a dict). Searches, AI
matching and CV builds register here as they move in (docs/roadmap.md)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Task

Handler = Callable[[Session, Task], dict[str, Any]]
HANDLERS: dict[str, Handler] = {}


def handler(kind: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        HANDLERS[kind] = fn
        return fn

    return register


@handler("ping")
def ping(_session: Session, task: Task) -> dict[str, Any]:
    """Proves the queue end to end (the Docker smoke test enqueues one)."""
    return {"pong": task.payload.get("message", "")}


@handler("search")
def search(session: Session, task: Task) -> dict[str, Any]:
    """Runs a saved search (app/search/runs.py)."""
    from app.search.runs import run_task

    return run_task(session, task.payload["run_id"])
