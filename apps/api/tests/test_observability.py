"""Logs and error reports: JSON lines with the right fields, a request id on
every request, nothing anyone typed in a log or an error report, and Sentry
only when it's asked for."""

from __future__ import annotations

import json
import logging

import pytest

from app.config import Settings
from app.observability import JsonFormatter, TextFormatter, init_sentry, scrub, setup_logging
from tests.conftest import auth


def record(msg="hello", **extra) -> logging.LogRecord:
    rec = logging.LogRecord("job_hunter.test", logging.INFO, __file__, 1, msg, None, None)
    for key, value in extra.items():
        setattr(rec, key, value)
    return rec


def test_json_lines():
    line = json.loads(JsonFormatter().format(record(request_id="abc123", status=200, user_id=7, unrelated="x")))
    assert line["msg"] == "hello" and line["level"] == "info" and line["logger"] == "job_hunter.test"
    assert (line["request_id"], line["status"], line["user_id"]) == ("abc123", 200, 7) and "unrelated" not in line
    assert line["ts"].endswith("+00:00")
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        failing = record()
        failing.exc_info = sys.exc_info()
    assert "ValueError: boom" in json.loads(JsonFormatter().format(failing))["error"]
    assert TextFormatter().format(record(kind="score")).endswith("hello [kind=score]")


def test_setup(monkeypatch):
    root = logging.getLogger()
    before = root.handlers[:]
    try:
        setup_logging(Settings(log_format="json", log_level="WARNING"))
        assert isinstance(root.handlers[0].formatter, JsonFormatter) and root.level == logging.WARNING
        assert logging.getLogger("uvicorn.access").disabled
    finally:
        root.handlers[:] = before
        root.setLevel(logging.WARNING)


def test_every_request_gets_an_id_and_one_log_line(client, user, caplog):
    caplog.set_level(logging.DEBUG, logger="job_hunter.requests")
    response = client.get("/applications", headers=auth(user.id), params={"q": "secret search words"})
    assert response.status_code == 200 and len(response.headers["x-request-id"]) == 16
    [line] = [r for r in caplog.records if r.name == "job_hunter.requests" and r.route == "/applications"]
    assert (line.method, line.status, line.user_id, line.levelno) == ("GET", 200, user.id, logging.INFO)
    assert line.duration_ms >= 0 and line.request_id == response.headers["x-request-id"]
    assert "secret" not in json.dumps({k: str(v) for k, v in vars(line).items()})  # no query strings

    kept = client.get("/me", headers={**auth(user.id), "x-request-id": "from-the-proxy-1234"})
    assert kept.headers["x-request-id"] == "from-the-proxy-1234"
    made_up = client.get("/me", headers={**auth(user.id), "x-request-id": "bad id\nwith newline"})
    assert made_up.headers["x-request-id"] != "bad id\nwith newline"

    caplog.clear()
    client.get(f"/applications/{'x' * 36}", headers=auth(user.id))
    [missing] = [r for r in caplog.records if r.name == "job_hunter.requests"]
    assert missing.route == "/applications/{application_id}" and missing.status == 404  # the route, not the id
    caplog.clear()
    client.get("/health")
    assert [r.levelno for r in caplog.records if r.name == "job_hunter.requests"] == [logging.DEBUG]  # health checks stay quiet
    client.get("/nowhere")
    assert caplog.records[-1].route == "(no route)"


def test_error_reports_carry_nothing_typed():
    event = {"request": {"url": "https://x/api", "method": "PUT", "data": {"summary": "my CV"}, "cookies": {"s": "1"},
                         "headers": {"authorization": "Bearer t"}, "query_string": "q=secret", "env": {"REMOTE_ADDR": "1.2.3.4"}},
             "user": {"id": 7, "email": "alex@example.com", "ip_address": "1.2.3.4"}}
    cleaned = scrub(event)
    assert cleaned["request"] == {"url": "https://x/api", "method": "PUT"} and cleaned["user"] == {"id": 7}


def test_sentry_only_when_asked():
    assert init_sentry("api", Settings(sentry_dsn="")) is False
    sentry_sdk = pytest.importorskip("sentry_sdk")
    try:
        assert init_sentry("worker", Settings(sentry_dsn="https://public@sentry.example.com/1", environment="test"))
        client = sentry_sdk.get_client()
        collected = client.options["data_collection"]
        assert client.is_active() and collected["user_info"] is False and collected["http_bodies"] == []
        assert collected["stack_frame_variables"] is False and collected["cookies"]["mode"] == "off"
        assert client.options["before_send"] is scrub and client.options["server_name"] == "worker"
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init()  # back to no client
