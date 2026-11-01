"""Logs and error reports for the API and the worker.

Logs: one line per event on stdout. LOG_FORMAT=json (the Docker default)
writes JSON - ts, level, logger, msg, and fields like request_id, user_id,
path, status, duration_ms, task_id - for any log collector; "text" is for
reading in a terminal. Requests are logged by account number and route,
never with bodies, query strings or anything typed into the app.

Errors: with SENTRY_DSN set, errors and error logs also go to Sentry
(sentry.io, or a self-hosted Sentry or GlitchTip). Without it, nothing is
sent anywhere. Request bodies, cookies, headers and IP addresses are
stripped before anything leaves.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import sys
import time
import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings, get_settings

FIELDS = ("request_id", "method", "route", "status", "duration_ms", "user_id", "task_id", "kind", "outcome", "attempt")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")

log = logging.getLogger("job_hunter.requests")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "ts": dt.datetime.fromtimestamp(record.created, dt.UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for field in FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                out[field] = value
        if record.exc_info:
            out["error"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        extra = " ".join(f"{f}={getattr(record, f)}" for f in FIELDS if getattr(record, f, None) is not None)
        return super().format(record) + (f" [{extra}]" if extra else "")


def setup_logging(settings: Settings | None = None) -> None:
    """Our format on the root logger; uvicorn's own loggers flow into it, and
    its access log is off - requests are logged by the middleware below."""
    settings = settings or get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.log_format == "json" else TextFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.log_level.upper())
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("botocore", "boto3", "urllib3", "httpx", "httpx2", "httpcore", "anthropic", "stripe"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class RequestLog:
    """ASGI middleware: a request id for each request (kept from X-Request-ID
    if it looks like one), sent back in the response, and one log line when
    it ends: method, route template, status, time and the account number."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex[:16]
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            route = getattr(scope.get("route"), "path", None) or "(no route)"
            level = logging.DEBUG if route == "/health" else logging.WARNING if status >= 500 else logging.INFO
            log.log(level, "%s %s %s", scope["method"], route, status, extra={
                "request_id": request_id, "method": scope["method"], "route": route, "status": status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "user_id": scope["state"].get("user_id"),
            })


# Sentry

_STRIPPED = ("data", "cookies", "headers", "env", "query_string")


def scrub(event: dict, _hint: dict | None = None) -> dict:
    """Takes out of an error report anything a person sent or typed: request
    bodies, cookies, headers, query strings and IP addresses."""
    request = event.get("request")
    if isinstance(request, dict):
        for key in _STRIPPED:
            request.pop(key, None)
    user = event.get("user")
    if isinstance(user, dict):
        event["user"] = {"id": user["id"]} if "id" in user else {}
    return event


def init_sentry(component: str, settings: Settings | None = None) -> bool:
    """Starts error reporting if SENTRY_DSN is set. True if it did."""
    settings = settings or get_settings()
    if not settings.sentry_dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=f"job-hunter@{settings.app_version}",
        server_name=component,  # api or worker, not the machine's name
        # Nothing about people: no user details, cookies, headers, bodies or
        # query strings, no SQL values, no AI prompts or answers, and no
        # local variables in stack traces (they could hold a CV).
        data_collection={
            "user_info": False,
            "cookies": {"mode": "off"},
            "http_headers": {"request": {"mode": "off"}},
            "http_bodies": [],
            "url_query_params": {"mode": "off"},
            "gen_ai": {"inputs": False, "outputs": False},
            "database_query_data": False,
            "queues": False,
            "stack_frame_variables": False,
        },
        traces_sample_rate=settings.sentry_traces_sample_rate,
        before_send=scrub,
        max_request_body_size="never",
    )
    sentry_sdk.set_tag("component", component)
    return True
