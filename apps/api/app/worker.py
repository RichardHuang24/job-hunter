"""The background worker: `python -m app.worker`. Claims tasks from the
Postgres queue (app/tasks/queue.py) and runs their handler; stops cleanly on
SIGTERM, between tasks.

It also queues daily saved searches when they're due (app/search/schedule.py).

`python -m app.worker --check` asks whether a worker is running: it queues a
ping and waits for one to answer (exit 0), or gives up (exit 1).

`python -m app.worker --alive` is the container's health check: the worker
touches a heartbeat file on every turn of its loop, and this exits 0 if that
happened recently (within a task lease, so a long task isn't "unhealthy").
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Task
from app.db.session import get_sessionmaker
from app.observability import init_sentry, setup_logging
from app.search.recheck import queue_recheck
from app.search.schedule import schedule_due
from app.tasks import queue
from app.tasks.handlers import HANDLERS

log = logging.getLogger("job_hunter.worker")
MAX_BACKOFF = 30.0  # seconds between tries while the database is unreachable


def heartbeat_file() -> Path:
    return Path(get_settings().worker_heartbeat_file or Path(tempfile.gettempdir()) / "job-hunter-worker.alive")


def beat(path: Path) -> None:
    try:
        path.touch()
    except OSError:  # a read-only filesystem only costs the health check
        pass


def alive(path: Path, max_age: float) -> bool:
    try:
        return time.time() - path.stat().st_mtime < max_age
    except OSError:
        return False


def run_one(sessions: sessionmaker[Session], worker: str, lease_seconds: int) -> bool:
    """Runs the next due task, if any. True when there was one."""
    with sessions() as session:
        task = queue.claim(session, worker, lease_seconds)
        if task is None:
            return False
        handler = HANDLERS.get(task.kind)
        fields = {"task_id": task.id, "kind": task.kind, "user_id": task.user_id, "attempt": task.attempts}
        started = time.perf_counter()
        try:
            if handler is None:
                raise LookupError(f"No handler for task kind '{task.kind}'")
            result = handler(session, task)
        except Exception as exc:  # noqa: BLE001 - any failure is recorded on the task, and retried
            session.rollback()
            log.exception("Task %s failed", task.kind, extra={
                **fields, "outcome": "failed", "duration_ms": round((time.perf_counter() - started) * 1000)})
            queue.fail(session, task, f"{type(exc).__name__}: {exc}")
        else:
            queue.succeed(session, task, result)
            log.info("Task %s succeeded", task.kind, extra={
                **fields, "outcome": "succeeded", "duration_ms": round((time.perf_counter() - started) * 1000)})
        return True


def check(sessions: sessionmaker[Session], timeout: float, poll: float = 0.5) -> bool:
    """Queues a ping and waits up to `timeout` seconds for a worker to run it."""
    with sessions() as session:
        task = queue.enqueue(session, "ping", {"message": "check"}, max_attempts=1)
        session.commit()
        task_id = task.id
    deadline = time.monotonic() + timeout
    while True:
        with sessions() as session:
            status = session.get(Task, task_id).status
        if status in ("succeeded", "failed"):
            return status == "succeeded"
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.worker")
    parser.add_argument("--check", action="store_true", help="exit 0 if a worker answers a ping, 1 if not")
    parser.add_argument("--timeout", type=float, default=30.0, help="seconds --check waits (default 30)")
    parser.add_argument("--alive", action="store_true", help="exit 0 if this container's worker loop ran recently")
    args = parser.parse_args()
    if args.alive:
        sys.exit(0 if alive(heartbeat_file(), get_settings().task_lease_seconds + 60) else 1)
    setup_logging()
    if args.check:
        ok = check(get_sessionmaker(), args.timeout)
        print("A worker answered." if ok else f"No worker answered within {args.timeout:g} s.")
        sys.exit(0 if ok else 1)
    worker = f"{socket.gethostname()}:{os.getpid()}"
    stopping = False

    def stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True
        log.info("Stopping after the current task")

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    init_sentry("worker")
    log.info("Worker %s started", worker)
    serve(get_sessionmaker(), worker, lambda: stopping)


def serve(sessions: sessionmaker[Session], worker: str, stopping: Callable[[], bool],
          sleep: Callable[[float], None] = time.sleep) -> None:
    """The worker's loop, until `stopping()`: queue due searches and job
    rechecks now and then, and run tasks. Nothing that goes wrong - the
    database restarting included - stops it; it waits and tries again."""
    settings = get_settings()
    last_schedule = last_recheck = float("-inf")
    heartbeat, backoff = heartbeat_file(), 0.0
    while not stopping():
        beat(heartbeat)
        if time.monotonic() - last_recheck >= settings.recheck_seconds:
            last_recheck = time.monotonic()
            try:
                with sessions() as session:
                    queue_recheck(session)
            except Exception:  # noqa: BLE001 - tries again next time
                log.exception("Couldn't queue a check for closed jobs")
        if time.monotonic() - last_schedule >= settings.schedule_seconds:
            last_schedule = time.monotonic()
            try:
                with sessions() as session:
                    if queued := schedule_due(session):
                        log.info("Queued %d daily search(es)", queued)
            except Exception:  # noqa: BLE001 - scheduling tries again next time
                log.exception("Couldn't schedule daily searches")
        try:
            ran = run_one(sessions, worker, settings.task_lease_seconds)
        except Exception:  # noqa: BLE001 - the database may be restarting: wait, then try again
            backoff = min(MAX_BACKOFF, max(1.0, backoff * 2))
            log.exception("Couldn't reach the task queue; trying again in %.0f s", backoff)
            sleep(backoff)
            continue
        backoff = 0.0
        if not ran:
            sleep(settings.worker_poll_seconds)

if __name__ == "__main__":
    main()
