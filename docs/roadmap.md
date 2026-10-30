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

## 2. Job search

- A connector interface for job sources, and the first connectors - only
  sources whose terms allow this use (see [third-party.md](third-party.md)).
- Saved searches per user, run on a schedule by the worker.
- Postings stored once and de-duplicated across sources; each user's view of
  a posting kept separately.

## 3. Ranking

- Scoring each posting against the profile, with the reasons.
- AI-assisted matching with a per-user budget.

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
