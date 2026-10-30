"""The background worker: `python -m app.worker`. Claims tasks from the
Postgres queue (app/tasks/queue.py) and runs their handler; stops cleanly on
SIGTERM, between tasks.

`python -m app.worker --check` asks whether a worker is running: it queues a
ping and waits for one to answer (exit 0), or gives up (exit 1).
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import sys
import time

from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Task
from app.db.session import get_sessionmaker
from app.tasks import queue
from app.tasks.handlers import HANDLERS

log = logging.getLogger("job_hunter.worker")


def run_one(sessions: sessionmaker[Session], worker: str, lease_seconds: int) -> bool:
    """Runs the next due task, if any. True when there was one."""
    with sessions() as session:
        task = queue.claim(session, worker, lease_seconds)
        if task is None:
            return False
        handler = HANDLERS.get(task.kind)
        try:
            if handler is None:
                raise LookupError(f"No handler for task kind '{task.kind}'")
            result = handler(session, task)
        except Exception as exc:  # noqa: BLE001 - any failure is recorded on the task, and retried
            session.rollback()
            log.exception("Task %s (%s) failed", task.id, task.kind)
            queue.fail(session, task, f"{type(exc).__name__}: {exc}")
        else:
            queue.succeed(session, task, result)
            log.info("Task %s (%s) succeeded", task.id, task.kind)
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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.check:
        ok = check(get_sessionmaker(), args.timeout)
        print("A worker answered." if ok else f"No worker answered within {args.timeout:g} s.")
        sys.exit(0 if ok else 1)
    settings = get_settings()
    worker = f"{socket.gethostname()}:{os.getpid()}"
    stopping = False

    def stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True
        log.info("Stopping after the current task")

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    sessions = get_sessionmaker()
    log.info("Worker %s started", worker)
    while not stopping:
        if not run_one(sessions, worker, settings.task_lease_seconds):
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
