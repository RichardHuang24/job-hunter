# Privacy

Job Hunter keeps personal data - people's profiles, CVs and applications -
so whoever runs a copy for other people is responsible for it under UK and
EU data protection law (UK GDPR, the Data Protection Act 2018, EU GDPR).
This page covers what the software does for you, and what's left to you.
It isn't legal advice.

## What people can do themselves

| Right | Where |
| --- | --- |
| See and take a copy of their data | Settings → Your data → **Download my data**: a ZIP with `data.json` (every row kept about them), `applications.csv`, their CV PDFs and a README (`GET /me/export`) |
| Correct it | Settings, Applications and CV are all editable |
| Delete it | Settings → Your data → **Delete my account**, after typing their email address (`DELETE /me`) |

The export leaves out sign-in secrets: session tokens and the tokens GitHub
or Google hand back. Deleting an account removes the person's files from
storage, then their account, which the database cascades to every table
holding their `user_id` - profile, roles, searches and runs, their view of
each job and its score, AI usage, applications and history, CV, documents,
tasks, sign-in sessions and links. Shared job postings stay; nothing of
theirs is in them. Tests check that no table keeps a row for a deleted
account (`apps/api/tests/test_privacy.py`).

## The privacy page

`/privacy` is public, linked from every page's footer and from sign-in. It
states what this deployment really does - read from its settings:

- whether AI scoring sends profiles and postings to Anthropic, or runs here;
- which job boards are asked (and that they only get search terms);
- where sign-in emails are sent from, and where PDFs are stored;
- whether Stripe is involved.

Fill in who you are before anyone else signs up - until then the page says
so:

| Setting | Meaning |
| --- | --- |
| `PRIVACY_CONTROLLER` | Your name, or your organisation's |
| `PRIVACY_CONTACT` | An email address for data requests and questions |

## What's left to you

- **Read the page and adapt it** if you do anything the software doesn't
  know about (more services, a different legal basis).
- **Processors:** check the terms of the services you use - your email
  provider, file storage, Anthropic (its commercial terms include a data
  processing addendum) and Stripe - and the safeguards for any transfer
  outside the UK or EU.
- **The ICO data protection fee:** in the UK, most organisations that
  handle personal data must
  [pay it](https://ico.org.uk/for-organisations/data-protection-fee/).
- **Backups:** deleted accounts stay in your database backups until they
  expire. Keep them only as long as you need to (docs/self-hosting.md).
- **Logs:** the API and worker log requests and tasks by account number,
  never CV text or notes (docs/admin.md). Rotate them.
- **Requests by email:** someone may ask you directly rather than use the
  buttons; you have a month to answer.

## Source code

The footer links to the source code, as the AGPL-3.0 asks of anyone who
lets others use the software over a network. If you run a modified copy,
point `SOURCE_URL` at your version.
