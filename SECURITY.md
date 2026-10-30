# Security

## Reporting a vulnerability

Please report security problems privately through GitHub:
**Security → Report a vulnerability** on this repository
([direct link](https://github.com/RichardHuang24/job-hunter/security/advisories/new)).
Don't open a public issue for them.

Include what you found, how to reproduce it, and what an attacker could do.
You'll get a reply within a week. Once a fix is out, the advisory is published
with credit to you, unless you'd rather stay anonymous.

## Supported versions

Job Hunter is in early development: only the latest `main` gets fixes.

## How the app is built to be safe

- The browser never calls the API directly. The web app checks the session,
  then forwards each request with a token that names the user and expires in
  60 seconds (`apps/web/src/lib/backend.ts`, `apps/api/app/auth.py`).
- Every user-owned table has a `user_id`, and every API query filters by the
  signed-in user.
- The forwarding route only passes plain path segments (no `..`, no encoded
  slashes) - `apps/web/src/lib/backendPath.ts`.
- Docker binds every port to `127.0.0.1`; in production only Caddy (80/443)
  is reachable.
- CI scans every commit for secrets (gitleaks) and personal data
  (`scripts/check_public_data.py`).
