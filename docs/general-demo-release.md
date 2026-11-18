# General public demo — 18 November 2026

Live project: https://jobs.richardhuang.dev

The public homepage now lets a visitor enter a target role without selecting
a fictional identity or supplying an email. Each visitor receives a separate
temporary account. Its target role is configured, a sample search is queued,
and its CV and application history start empty. Known roles can provide
title synonyms; custom roles are also accepted. No biography, contact details,
qualifications or skills are inferred from the chosen title.

Visitors can edit and save their own CV, generate a PDF, export their data and
delete the workspace. Workspaces expire after 24 hours. A CV is separate from
the profile used for search preferences. Optional sample walkthroughs remain
available behind a disclosure on the public entry page.

The deployment continues to use fictional job postings, local simulated fit
scores and no billing. It does not send job applications or make paid model
calls. Email and OAuth sign-in providers are disabled for this public mode.

## Verification

- API suite: 252 passed, five skipped environment-dependent checks.
- Web: 25 unit tests, type check, lint and production build passed.
- [CI passed for the runtime commit](https://github.com/RichardHuang24/job-hunter/actions/runs/44390648806), including SQLite/PostgreSQL, secret/data checks and Docker browser journeys on both amd64 and arm64.
- An isolated PostgreSQL/worker/storage stack passed the visitor journey before activation.
- The same journey passed on public HTTPS: role entry, empty CV, authored CV
  saved across reload, actual PDF generation/download, independent users and
  inaccessible cross-user PDF files.
- CV layouts passed at 390, 768 and 1440 pixels after correcting grid sizing
  when a generated PDF is present. The public entry page also passed at 390px.
- The optional sample walkthrough, export/deletion and all existing pages in
  phone/dark/desktop layouts passed in staging.
- The public share image is 1200 × 630 PNG, accessible without login.
- LinkedIn's crawler user-agent received the Open Graph title, description
  and public image in the HTML head. Secure HttpOnly session cookies and
  disabled external sign-in providers were checked over HTTPS.

These are functional checks of the demonstration. They do not measure hiring
outcomes, scoring accuracy or production capacity. Four production dependency
audit findings remain in the existing Nodemailer/Auth.js dependency chain;
the demo does not register those email/OAuth providers. Updating that chain
is separate work before offering email-based permanent accounts.

## Deployment and rollback

Runtime source: `61fa82540fc574c9a707cc85898b8e8af5c07b3b`.
Production still uses the existing database, file store, domain and HTTPS proxy.
The database was backed up before activation. No existing account data was reset.

The deployed image tags are `job-hunter-api:general-61fa825` and
`job-hunter-web:general-61fa825`, also tagged `:local` for the existing Compose
wrapper. Prior images are retained as `job-hunter-api:before-general-20261118`
and `job-hunter-web:before-general-20261118`. Retag those as `:local` and run
the existing Compose wrapper with `up -d --no-build --wait api worker web` to
roll the application images back. The database schema was not changed.

The staging stack has its own project, database and storage. Its containers
and volumes are removed after public verification; production resources are
retained. Source attribution and AGPL source access remain in place.

## LinkedIn

Use the public project URL above for a link preview. [The English launch draft](linkedin-launch.md)
and [the share image](images/general-share.png) are ready. No LinkedIn post has
been sent automatically.
