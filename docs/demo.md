# A demo site

Demo mode turns Job Hunter into a public site anyone can try without signing up.
The public homepage starts with one question: **What role are you looking for?**
Entering a title creates an independent visitor account with that target role,
a queued sample search, an empty application tracker and a completely blank CV.
No name, email, employer, skills or work history is invented for the visitor.
Known role names can supply matching title synonyms; unlisted roles use the
general preset. Settings remains available for location, eligibility and skills.

The public deployment uses fictional sample jobs and simulated scores, clearly
labelled on the homepage and inside the workspace. A title outside the sample
dataset may return no matches; the app does not fabricate postings. CV edits are
separate from the search profile. Visitors can save a CV, generate a PDF,
export their data and delete their workspace.

Each workspace expires after `DEMO_ACCOUNT_HOURS` (24 by default). Export work
you want to keep; this is a temporary project demo, not a permanent account
service. Email and OAuth providers are disabled in demo mode.

The optional **Prefer a ready-made walkthrough?** section still offers three
fictional people, each with an explicit sample CV and applications:

| Person | Who | Arrives with |
| --- | --- | --- |
| Jo Example | A registered nurse in Manchester, after a Band 6 post | 4 matches, 1 flagged, 1 filtered out; an interview in 2 days; a rejection; a CV |
| Sam Example | A data analyst in Leeds, open to remote work | 4 matches, 2 filtered out; a take-home test in 3 days; a CV |
| Alex Example | A backend engineer in London, after hybrid or remote work | 5 matches, 3 filtered out; an offer to reply to; a CV |

Choosing one makes a fresh account just for that visitor - nobody sees
anyone else's changes - already set up as that person: profile and target
roles, a search run against the built-in sample jobs and scored, a saved
job, applications at different stages with their history, and a CV with its
PDF. They can use everything: search again, score jobs, track applications,
edit the CV and make PDFs, download their data, delete the account.

The optional sample profiles, jobs and companies are fictional. Custom
workspaces contain only the details visitors enter. Demo accounts use addresses
at `demo.invalid`, which can't receive email, and are deleted - files and
all - `DEMO_ACCOUNT_HOURS` (24) after they were made. A banner on every page
says so.

## Running one

It's the same as [self-hosting](self-hosting.md), on its own domain (say
`demo.example.com`), with these in `.env`:

```sh
DEMO_MODE=true
DEMO_ACCOUNT_HOURS=24
JOB_SOURCES=demo        # the built-in sample jobs - the demo people are built on them
AI_PROVIDER=simulated   # free; or keep Claude with a small allowance, below
BILLING_ENABLED=false
PRIVACY_CONTROLLER=...  # the privacy page still applies
PRIVACY_CONTACT=...
```

Then:

```sh
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

The production setup asks for `EMAIL_SERVER`, but a demo site sends no
email - email and OAuth providers are disabled in demo mode - so any SMTP address will do.

To show real Claude scores instead of simulated ones, set
`ANTHROPIC_API_KEY` and keep each visitor's allowance small, for example
`AI_SCORES_PER_MONTH=20` and `AI_BUDGET_USD_PER_MONTH=0.05`; scores then run
on the worker as usual, and each demo person's first jobs are scored a few
seconds after they arrive.

## Limits

- **Per visitor:** 20 new demo accounts an hour from one address (the web
  app counts them).
- **Overall:** `DEMO_ACCOUNTS_PER_HOUR` (300) new demo accounts an hour;
  past that, visitors are asked to try again in a few minutes.
- **Lifetime:** the worker deletes demo accounts older than
  `DEMO_ACCOUNT_HOURS` every minute, so the site never fills up.

A demo account is small - a few dozen rows and a 40 KB PDF - so a 2 GB
server holds thousands at once.

## On your main site

Leave `DEMO_MODE=false`. The demo's sign-in page replaces the email sign-in,
so nobody can make a real account on a demo site, and the admin page -
which needs a real sign-in - isn't reachable there; look after a demo site
from its server (`docker compose logs`).

## How it works

`apps/api/app/demo.py` holds the demo people and sets an account up through
the same steps as onboarding; `apps/web/src/app/demo/start/route.ts` makes
the account and its sign-in session when a visitor chooses someone, after
checking the request came from the site itself. The demo mode run in CI
(`scripts/browser_test.py --demo`) tries Jo end to end on every push.
