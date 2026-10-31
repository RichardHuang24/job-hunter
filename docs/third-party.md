# Third-party software and data

## Software

Job Hunter's own code is AGPL-3.0. It is built on these projects, each under
its own license:

| Project | Used for | License |
| --- | --- | --- |
| [ai-job-search](https://github.com/MadsLorentzen/ai-job-search) | Origin of this project | MIT ([notice](../LICENSES/ai-job-search-MIT.txt)) |
| [Next.js](https://nextjs.org), [React](https://react.dev) | Web app | MIT |
| [Auth.js](https://authjs.dev) (`next-auth`, `@auth/pg-adapter`) | Sign-in | ISC |
| [Tailwind CSS](https://tailwindcss.com) | Styles | MIT |
| [node-postgres](https://node-postgres.com) (`pg`) | Web app's database access | MIT |
| [Nodemailer](https://nodemailer.com) | Sign-in emails | MIT-0 |
| [jose](https://github.com/panva/jose) | Signing API tokens | MIT |
| [FastAPI](https://fastapi.tiangolo.com), [Pydantic](https://docs.pydantic.dev) | API | MIT |
| [Uvicorn](https://www.uvicorn.org) | API server | BSD-3-Clause |
| [SQLAlchemy](https://www.sqlalchemy.org), [Alembic](https://alembic.sqlalchemy.org) | Database models, migrations | MIT |
| [psycopg](https://www.psycopg.org) | API's Postgres driver | LGPL-3.0 |
| [PyJWT](https://pyjwt.readthedocs.io) | Checking API tokens | MIT |
| [HTTPX](https://github.com/encode/httpx) (`httpx2`) | Calling job sources | BSD-3-Clause |
| [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) | AI scoring | Apache-2.0 |
| [PostgreSQL](https://www.postgresql.org) | Database | PostgreSQL License |
| [Caddy](https://caddyserver.com) | HTTPS in production | Apache-2.0 |
| [Mailpit](https://mailpit.axllent.org) | Catching email in development | MIT |

The exact versions are in `apps/web/package-lock.json` and
`apps/api/requirements.txt`.

## Services

| Service | Used for | Needed |
| --- | --- | --- |
| [Anthropic API](https://www.anthropic.com/api) (Claude) | AI scoring - your profile and the posting are sent; see [ai-scoring.md](ai-scoring.md) | Only when `ANTHROPIC_API_KEY` is set |
| [Himalayas API](https://himalayas.app/api), [Jobicy API](https://jobicy.com/jobs-rss-feed) | Remote job listings - only the search terms and countries are sent, never anything about a person | When `JOB_SOURCES` includes them |

## Job data

Before a job source is added, its terms of use are read and recorded here:
whether automated access is allowed, whether commercial use is, and what
attribution it asks for. A source whose terms don't allow this use -
including any that forbids scraping - isn't added. How to add one:
[job-sources.md](job-sources.md).

| Source | Key | Commercial use | Notes |
| --- | --- | --- | --- |
| Sample jobs | `demo` | Yes - our own data | Built-in postings with fictional employers, for trying Job Hunter out |
| [Himalayas](https://himalayas.app/api) | `himalayas` | Yes - "personal and commercial integrations" ([API terms](https://himalayas.app/terms)) | Remote jobs. Apply links unchanged; a visible link credits Himalayas; jobs shown only on sites you run and never passed to other job boards or aggregators (no feeds, no JobPosting markup); expired and closed jobs taken down. Free; key optional |
| [Jobicy](https://jobicy.com/jobs-rss-feed) | `jobicy` | Yes - "commercial use, job boards, aggregators, and redistribution are permitted" | Remote jobs from the last 7 days. Jobicy credited with a link; apply links go to the Jobicy job page; feed read at most hourly; closed jobs taken down. Free, no key |

Terms as published on 31 October 2026 - they can change, so re-read them
before relying on a source for a paid service.
