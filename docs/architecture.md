# Architecture

Job Hunter is two apps, a database and a file store, deployed as one Docker
Compose stack.

```mermaid
flowchart LR
    B[Browser] -- "session cookie" --> W
    subgraph stack [Docker Compose]
        W["web<br/>Next.js 16 + Auth.js v5"]
        A["api<br/>FastAPI"]
        K["worker<br/>python -m app.worker"]
        M["migrate<br/>alembic upgrade head"]
        D[(Postgres 17)]
        S[("storage<br/>S3-compatible")]
    end
    W -- "/api/backend/* forwarded<br/>with a signed token" --> A
    W -- "users, sessions" --> D
    A --> D
    A -- "downloads" --> S
    K -- "task queue" --> D
    K -- "CV PDFs" --> S
    M -. "runs first" .-> D
```

## The pieces

| Service | What it does | Code |
| --- | --- | --- |
| `web` | Pages, sign-in, and the only door to the API | `apps/web` |
| `api` | Every feature's logic and data, per user | `apps/api/app` |
| `worker` | Runs searches, AI scoring and CV PDF builds (LuaLaTeX) from the queue; queues daily searches and checks for closed jobs | `apps/api/app/worker.py` |
| `migrate` | Brings the schema up to date, then exits; the others wait for it | `apps/api/alembic` |
| `db` | Postgres: users, sessions, profiles, searches, jobs, scores, CVs, tasks - everything but files | |
| `storage` | Generated files (CV PDFs), through the S3 API: the [Versity S3 Gateway](https://github.com/versity/versitygw), keeping plain files in a volume - or Cloudflare R2, AWS S3 and the like | `apps/api/app/storage.py` |
| `stripe` | Development only, `--profile billing`: forwards Stripe test events to the API ([billing.md](billing.md)) | |
| `mailpit` | Development only: catches outgoing email | |
| `caddy` | Production only: HTTPS in front of `web`, and Stripe's webhook to `api` | `deploy/Caddyfile` |

## A request, end to end

1. The browser asks the web app for `/api/backend/me`.
2. `app/api/backend/[...path]/route.ts` checks the Auth.js session (stored in
   Postgres). No session: `401`.
3. It checks the path is plain segments only (`src/lib/backendPath.ts`), then
   signs a JWT - HS256, `sub` = the user's id, 60-second expiry - with
   `BACKEND_JWT_SECRET` (`src/lib/backend.ts`).
4. The API verifies the token's signature, issuer, audience and expiry
   (`app/auth.py`), loads the user, and runs the endpoint. Endpoints read and
   write only that user's rows.

Server components skip the hop and call the API directly with the same token
(`src/lib/session.ts`). The API is never exposed outside the stack, with one
exception: in production Caddy sends `/billing/webhook` straight to it,
because Stripe calls that path itself - Stripe's signature is checked there
instead of a user token ([billing.md](billing.md)).

## Sign-in

Auth.js v5 with database sessions (`@auth/pg-adapter`). Providers switch on
from the environment: an emailed link when `EMAIL_SERVER` is set, GitHub and
Google when their client id and secret are. `src/proxy.ts` (Next.js 16's
name for middleware) sends signed-out visitors to `/signin`.

Alembic owns every table, including the four Auth.js ones (`users`,
`accounts`, `sessions`, `verification_token`), so one migration history
describes the whole database.

## Background work

`app/tasks/queue.py` is a queue on Postgres. A worker claims the oldest due
task with `SELECT ... FOR UPDATE SKIP LOCKED`, so several workers never take
the same task. A task whose worker died is claimed again once its lease
(`TASK_LEASE_SECONDS`, 10 minutes) runs out. Failures retry after 30 s, 2 min,
8 min..., until the task's attempts are used up.

Handlers register by kind in `app/tasks/handlers.py`. `python -m app.worker
--check` queues a `ping` and waits for an answer - a quick way to see that a
worker is running.

## Profiles, presets and job titles

Industries and markets live in [`presets/`](../presets/README.md) as TOML
files, loaded and cross-checked once by `app/presets` (`GET /presets`,
`/presets/industries/{key}`, `/presets/markets/{key}`). Each industry brings
its roles (the job titles each covers and the terms to search for), suggested
skills, scoring weights and seniority words, so supporting a new field is a
new file, not code.

A profile (`profiles`) holds the person's industry and market, the levels
they want, skills and languages, and the deal-breakers: locations, work
arrangements, the countries they can work in without a visa, and a minimum
salary. Their **target roles** (`profile_targets`) start from the industry's
preset roles in onboarding (`POST /me/onboarding`) and can be edited freely
(`PUT /me/targets`).

`app/matching/titles.py` reads a job title against those target roles: which
role it is (the longest matching phrase wins; exclusions knock a role out)
and how senior it is. `POST /me/title-check` runs it for one title, so people
can see how job search will read a posting before job search exists.

## Job search

A **saved search** (`saved_searches`) holds terms, places and countries.
Running one creates a `search_runs` row and queues a `search` task; the
worker does the work (`app/search/runs.py`):

1. The search becomes queries - every term in every place
   (`app/search/queries.py`).
2. Each enabled **job source** (`app/sources/`, see
   [job-sources.md](job-sources.md)) that covers the query's countries is
   asked. A source that fails is recorded on the run; the others carry on.
3. Postings go into the shared **`jobs`** table - one row per source and
   source id, updated on every sighting. A fingerprint of company, title and
   place stops the same job from two sources showing twice.
4. Each job the user hasn't seen gets a **`user_jobs`** row: which of their
   roles it is, its level, and the deal-breaker checks
   (`app/matching/evaluate.py`) - role, level, arrangement, location, work
   permit, salary - each pass, flag, fail or unknown, with the reason. Any
   fail files the job under "Filtered out"; any flag under "Flagged".

Changing the profile or the target roles re-judges every job the user has.
Daily searches are queued by the worker itself (`app/search/schedule.py`,
with `SKIP LOCKED` so several workers never queue the same search twice).

## AI scoring

After a search, the run queues a `score` task for its new matches and
flagged jobs; **Score this job** queues one on its own. The worker builds a
request per job (`app/scoring/prompt.py`) - the person's profile as a cached
system prompt, the posting and its checks in the user turn - and sends it to
Claude, or to the simulator when there's no API key
(`app/scoring/providers.py`). The answer's quotes are checked against the
posting, the overall score is weighted by the industry preset, and the
result is stored in `job_scores`, one per user job. Every call is recorded
in `ai_usage`, which the monthly allowance is checked against before each
call. Details: [ai-scoring.md](ai-scoring.md).

## CVs and files

Each person's CV is structured data in `cvs` (`app/cv/schema.py`) - started
from their profile until they save it. **Make PDF** queues a `cv_pdf` task;
the worker turns the CV into LaTeX with every piece of text escaped
(`app/cv/latex.py`), builds it with LuaLaTeX in a sealed-off folder
(`app/cv/build.py`), and puts the PDF in storage (`app/storage.py`) under
`users/<id>/documents/<id>.pdf`. The `documents` table tracks each file;
downloads go through the API, to their owner only. Details: [cv.md](cv.md).

## Billing

Off by default (`BILLING_ENABLED=false`): every feature is free. When it's
on, Stripe's signed webhook events are recorded once each in
`billing_events` (`app/billing.py`); plans and checkout come with the hosted
version. Details: [billing.md](billing.md).

## Where the rest goes

See [roadmap.md](roadmap.md). The applications tracker, tailored CVs and
paid plans all follow the same rules: data scoped to the user, slow work on
the worker, every call through the API.
