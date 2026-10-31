# Contributing

Thanks for helping. Job Hunter is early, so the shape of things still moves -
for anything bigger than a fix, open an issue first so we can agree on the
approach.

## Set up

Turn on the repo's git hooks once per clone. They stop a commit or push that
would publish an email address, a phone number, a `.env` file or a database:

```sh
git config core.hooksPath .githooks
```

Optionally list words that must never appear in the repo - your name, your
employer, client names - one per line in `~/.config/job-hunter/denylist.txt`.
The hooks check against it; the file never leaves your machine. Installing
[gitleaks](https://github.com/gitleaks/gitleaks) lets the pre-commit hook scan
for secrets too (CI always does).

## Run it

The quickest way is Docker (see the README). To work on one app with hot
reload, run the database and Mailpit in Docker and the app itself directly:

```sh
./scripts/setup-env.sh
docker compose up db mailpit
```

**API** (Python 3.12):

```sh
cd apps/api
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
export DATABASE_URL="postgresql+psycopg://jobhunter:<POSTGRES_PASSWORD from .env>@localhost:5432/jobhunter"
export BACKEND_JWT_SECRET="<from .env>"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8420
.venv/bin/python -m app.worker        # in another terminal
```

**Web** (Node 22.18 or newer): put the same values in `apps/web/.env.local` -
`DATABASE_URL` (written `postgresql://...`, without `+psycopg`), `AUTH_SECRET`,
`BACKEND_JWT_SECRET`, `BACKEND_URL=http://localhost:8420`,
`EMAIL_SERVER=smtp://localhost:1025` - then:

```sh
cd apps/web
npm install
npm run dev                           # http://localhost:3420
```

## Test

```sh
cd apps/api && .venv/bin/pytest       # SQLite; set TEST_DATABASE_URL to run on Postgres
cd apps/web && npm run lint && npm run typecheck && npm test
python3 scripts/smoke_test.py         # against a running stack
```

CI runs all of these, builds the Docker images, and runs the smoke test
against them.

## Conventions

- **Everything a user owns is scoped to them.** A new table gets a `user_id`;
  a new endpoint depends on `current_user` and filters by it. Add a test that
  one user can't see another's data.
- **Alembic owns the schema**, including the Auth.js tables. Change the models,
  then `alembic revision --autogenerate -m "..."`, and read the result.
- **The browser talks only to the web app.** Client code calls
  `/api/backend/...` through `src/lib/api.ts`; server components use
  `src/lib/session.ts`.
- **No real people in fixtures or examples.** Use `@example.com` addresses and
  made-up names and companies.
- **Industries and markets are data.** To support a new field or country,
  add a file under `presets/` - see [presets/README.md](presets/README.md).
- **Job sources:** a connector is only merged once the source's terms allow
  the use - see [docs/job-sources.md](docs/job-sources.md) and
  [docs/third-party.md](docs/third-party.md).

By contributing, you agree that your contributions are licensed under the
project's license (AGPL-3.0).
