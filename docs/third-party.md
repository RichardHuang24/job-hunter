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
| [httpx2](https://pypi.org/project/httpx2/) | Calling job sources | BSD-3-Clause |
| [boto3](https://github.com/boto/boto3) | File storage over the S3 API | Apache-2.0 |
| [Stripe Python library](https://github.com/stripe/stripe-python) | Checking Stripe webhook signatures | MIT |
| [Sentry Python SDK](https://github.com/getsentry/sentry-python) (`sentry-sdk`) | Error reports, only when `SENTRY_DSN` is set | MIT |
| [TeX Live](https://tug.org/texlive/): LuaLaTeX, fontspec, geometry, xcolor, hyperref | Building CV PDFs (installed from Debian in the API image) | LPPL-1.3c and GPL-2.0-or-later, per package |
| [Lato](https://www.latofonts.com) (`fonts-lato`) | The CV font, embedded in each PDF | OFL-1.1 |
| [DejaVu fonts](https://dejavu-fonts.github.io) (`fonts-dejavu-core`) | Characters Lato lacks, in CV PDFs | Bitstream Vera license |
| [Versity S3 Gateway](https://github.com/versity/versitygw) | The file store in the Docker setup | Apache-2.0 |
| [Stripe CLI](https://github.com/stripe/stripe-cli) | Forwarding Stripe test events in development (`--profile billing`) | Apache-2.0 |
| [Playwright](https://playwright.dev), [Pillow](https://python-pillow.org) | The browser test and the README pictures (development only) | Apache-2.0, MIT-CMU |
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
| [Sentry](https://sentry.io), or a self-hosted Sentry or GlitchTip | Error reports - the error and its stack trace, without user details, request data or local variables ([admin.md](admin.md)) | Only when `SENTRY_DSN` is set |
| [Stripe](https://stripe.com) | Billing - Stripe sends events to the webhook; nothing about a person is sent to Stripe yet | Only when `BILLING_ENABLED=true` |
| Cloudflare R2, AWS S3 or another S3-compatible service | Keeping generated files (CV PDFs) instead of the built-in file store | Only when `S3_*` point there |

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
