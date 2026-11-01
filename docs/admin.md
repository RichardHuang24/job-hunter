# Running it: the admin page, logs and error reports

## The admin page

`/admin` shows how this Job Hunter is doing. Only the addresses in
`ADMIN_EMAILS` (comma-separated, any case) see it; for everyone else it
doesn't exist (404), and the API answers `403`. Admins also get an **Admin**
link in the menu.

| Section | What it shows |
| --- | --- |
| Tiles | People (and how many finished the setup, and are new this week), AI spend and scores this month, tasks waiting (and for how long, and any stuck), CV PDFs made this week |
| AI costs this month | Per person: scores, tokens in and out, cost, and how much of their monthly budget (`AI_BUDGET_USD_PER_MONTH`) is used |
| Job sources, last 7 days | Per source: in how many search runs it was asked, how many of those it failed (the error rate), jobs found, its latest error and when, and the latest check for closed jobs |
| Task queue | Per kind of task: waiting, running, done and failed in the last 24 hours; tasks running past their lease (a worker may have died - another takes them over); the latest failures |

It reads the database only (`GET /admin/overview`, `apps/api/app/admin.py`).

## Logs

The API and the worker write one line per event to stdout - `docker compose
logs api worker`. In Docker they're JSON (`LOG_FORMAT=json`), for any log
collector; set `LOG_FORMAT=text` to read them in a terminal.

```json
{"ts": "2026-11-01T10:51:02.852+00:00", "level": "info", "logger": "job_hunter.requests", "msg": "GET /admin/overview 200", "request_id": "42e825bbd0a74aea", "method": "GET", "route": "/admin/overview", "status": 200, "duration_ms": 12.7, "user_id": 1}
{"ts": "2026-11-01T10:51:02.804+00:00", "level": "info", "logger": "job_hunter.worker", "msg": "Task search succeeded", "task_id": "14f94f66-...", "kind": "search", "user_id": 1, "outcome": "succeeded", "duration_ms": 29, "attempt": 1}
```

- **Requests:** one line each, with a request id (also sent back as
  `X-Request-ID`, or kept from the incoming header), the route *template*
  (`/applications/{application_id}`, not the id), status, time and account
  number. Health checks log at debug level.
- **Tasks:** one line each, with the kind, outcome, time, attempt and
  account number. A failed task logs its error.
- **Never logged:** request bodies, query strings, CV text, notes, search
  terms, email addresses. People are referred to by account number.

```sh
docker compose logs --no-log-prefix api | jq 'select(.status >= 500)'
docker compose logs --no-log-prefix worker | jq 'select(.outcome == "failed")'
```

`LOG_LEVEL` (default `INFO`) sets how much is logged. Docker keeps the logs;
set up rotation (Docker's `json-file` driver with `max-size`, or your log
collector) so they don't fill the disk.

## Error reports (Sentry)

Off by default: with `SENTRY_DSN` empty, nothing is sent anywhere. To get an
email when something breaks, with the stack trace:

1. Make a project on [sentry.io](https://sentry.io) (its free plan is
   enough for one server), or run your own Sentry or
   [GlitchTip](https://glitchtip.com) (which speaks the same protocol).
2. Put its DSN in `.env` as `SENTRY_DSN`, and restart:
   `docker compose up -d api worker`.

Errors in the API and the worker, and anything they log as an error, are
reported, tagged `api` or `worker`. What leaves the server is kept to the
error itself: no user details, cookies, headers, request bodies or query
strings, no SQL values, no AI prompts or answers, and no local variables in
stack traces, since they could hold someone's CV
(`apps/api/app/observability.py`). Mention Sentry on your privacy page if you
use it. `SENTRY_TRACES_SAMPLE_RATE` (default `0`) turns on performance
tracing for that share of requests.

The web app doesn't report to Sentry yet; its errors are in
`docker compose logs web`.
