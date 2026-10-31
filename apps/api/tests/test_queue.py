"""The Postgres task queue and the worker."""

from __future__ import annotations

import datetime as dt
import os
import threading
import time

from app.db.models import Task
from app.tasks import queue
from app.tasks.handlers import HANDLERS
from app.worker import alive, beat, check, run_one, serve

NOW = dt.datetime(2026, 10, 30, 12, 0, tzinfo=dt.UTC)


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def test_a_task_is_claimed_once_and_in_order(sessions):
    with sessions() as session:
        first = queue.enqueue(session, "ping", {"message": "1"}, run_after=NOW - dt.timedelta(minutes=2))
        queue.enqueue(session, "ping", {"message": "2"}, run_after=NOW - dt.timedelta(minutes=1))
        queue.enqueue(session, "ping", {"message": "later"}, run_after=NOW + dt.timedelta(hours=1))
        session.commit()
        first_id = first.id
    with sessions() as session:
        claimed = queue.claim(session, "w1", lease_seconds=600, now=NOW)
        assert claimed.id == first_id and claimed.status == "running" and claimed.attempts == 1
        assert queue.claim(session, "w2", lease_seconds=600, now=NOW).payload == {"message": "2"}
        assert queue.claim(session, "w3", lease_seconds=600, now=NOW) is None  # the third isn't due yet


def test_a_failure_is_retried_later_then_given_up(sessions):
    with sessions() as session:
        queue.enqueue(session, "ping", max_attempts=2, run_after=NOW)
        session.commit()
    with sessions() as session:
        task = queue.claim(session, "w1", 600, now=NOW)
        queue.fail(session, task, "boom", now=NOW)
        assert task.status == "queued" and _aware(task.run_after) == NOW + dt.timedelta(seconds=30)
        assert queue.claim(session, "w1", 600, now=NOW) is None  # backing off
        task = queue.claim(session, "w1", 600, now=NOW + dt.timedelta(seconds=31))
        queue.fail(session, task, "boom again", now=NOW)
        assert (task.status, task.attempts, task.error) == ("failed", 2, "boom again")


def test_a_task_whose_worker_died_is_claimed_again(sessions):
    with sessions() as session:
        queue.enqueue(session, "ping", run_after=NOW)
        session.commit()
    with sessions() as session:
        queue.claim(session, "dead-worker", 600, now=NOW)
        assert queue.claim(session, "w2", 600, now=NOW + dt.timedelta(seconds=599)) is None
        retaken = queue.claim(session, "w2", 600, now=NOW + dt.timedelta(seconds=601))
        assert retaken.locked_by == "w2" and retaken.attempts == 2


def test_the_worker_runs_a_task_and_records_failures(sessions):
    with sessions() as session:
        ok = queue.enqueue(session, "ping", {"message": "hello"})
        unknown = queue.enqueue(session, "no-such-kind", max_attempts=1)
        session.commit()
        ok_id, unknown_id = ok.id, unknown.id
    assert run_one(sessions, "w1", 600) is True
    assert run_one(sessions, "w1", 600) is True
    assert run_one(sessions, "w1", 600) is False  # empty
    with sessions() as session:
        assert session.get(Task, ok_id).result == {"pong": "hello"}
        failed = session.get(Task, unknown_id)
        assert failed.status == "failed" and "No handler" in failed.error
    assert "ping" in HANDLERS


def test_the_check_answers_only_when_a_worker_runs(sessions):
    assert check(sessions, timeout=0, poll=0) is False  # nobody is running tasks

    stop = threading.Event()

    def worker():
        while not stop.is_set():
            if not run_one(sessions, "w1", 600):
                time.sleep(0.05)

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert check(sessions, timeout=5, poll=0.05) is True
    finally:
        stop.set()
        thread.join()


def test_the_heartbeat_says_whether_the_loop_runs(tmp_path):
    path = tmp_path / "alive"
    assert not alive(path, 60)  # never started
    beat(path)
    assert alive(path, 60)
    os.utime(path, (time.time() - 120, time.time() - 120))
    assert not alive(path, 60)  # stuck for longer than allowed


def test_the_loop_survives_the_database_going_away(sessions, tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("WORKER_HEARTBEAT_FILE", str(tmp_path / "alive"))
    get_settings.cache_clear()
    with sessions() as session:
        queue.enqueue(session, "ping", {"message": "after the outage"})
        session.commit()

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] <= 6:  # the first turns: the database is down
            raise ConnectionError("database restarting")
        return sessions()

    waits: list[float] = []
    turns = iter(range(12))
    serve(flaky, "w1", lambda: next(turns, None) is None, sleep=waits.append)
    assert waits[:2] == [1.0, 2.0]  # backing off while it's down
    assert alive(tmp_path / "alive", 60)
    with sessions() as session:
        [task] = session.query(Task).filter_by(kind="ping").all()
        assert task.status == "succeeded" and task.result == {"pong": "after the outage"}
