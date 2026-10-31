# Roadmap

Job Hunter is being built in the open, one working milestone at a time. Each
milestone ships with tests, runs in the Docker stack, and passes the
end-to-end smoke test in CI.

## 0. Foundation - done

- Accounts: email-link sign-in, optional GitHub and Google (Auth.js).
- Profiles with an industry and market from shared presets.
- The API door: session check, short-lived signed tokens, per-user data.
- Background worker on a Postgres queue.
- Docker Compose for local use; a production setup with Caddy and HTTPS.
- CI: tests on SQLite and Postgres, lint, types, build, secret and
  personal-data scans, and an end-to-end run against the Docker images.

## 1. Profiles and presets - done

- Twelve industry presets and seven job markets, as data files
  ([`presets/`](../presets/README.md)): roles with the job titles they cover
  and search terms, suggested skills, scoring weights, seniority words;
  currencies, countries and common locations.
- Reading job titles: which target role a title is, and how senior.
- A full profile: experience, levels wanted, skills, languages, and the
  deal-breakers - locations, work arrangements, work permits, minimum salary.
- A four-step onboarding, editable target roles in Settings, and a "check a
  job title" tool that shows how job search will read a posting.

## 2. Job search - done

- A job source interface, with a registry that knows where each source has
  jobs and whether its terms allow commercial use
  ([job-sources.md](job-sources.md)).
- Built-in sample jobs with fictional employers, so everything works on the
  first run.
- Saved searches per user - the first made from the profile at the end of
  onboarding - run daily by the worker or on demand.
- Postings stored once and de-duplicated across sources; each user's view of
  a posting kept separately: its role, level, deal-breaker checks, and saved
  or hidden.
- Deal-breaker checks: role, level, work arrangement, location, work permit
  and salary, each explained.

- Real remote jobs from Himalayas and Jobicy, used within their terms:
  credited on every job, closed and expired jobs taken down, and remote jobs
  carrying the countries they're open to for the work-permit check.

Still to come: job boards for on-site and hybrid work, each added once its
terms are cleared ([third-party.md](third-party.md)).

## 3. Ranking - done

- Every new match and flagged job is scored 0-100 for fit, in the
  background, with a reason for each of four dimensions weighted by the
  industry preset, requirements quoted from the posting (and checked to be
  there), gaps, risks and what the posting doesn't say.
- Claude through the Anthropic API when a key is set - Haiku 5.5 at low
  effort with thinking off by default, under $0.001 a score - and a free,
  clearly labelled simulated scorer when not ([ai-scoring.md](ai-scoring.md)).
- A monthly allowance per user (scores and dollars), a usage ledger with
  the cost of every call, and "best fit first" sorting.

## 4. Applications

- Track each application from saved to offer, with dates and notes.
- A dashboard of where everything stands.

## 5. CV workbench

- CV content kept as structured data, with a tailored PDF per job.
- Storage for generated documents.

## 6. Hosted version

- Billing with Stripe, usage limits per plan.
- A public demo.

Self-hosting stays free under the AGPL.
