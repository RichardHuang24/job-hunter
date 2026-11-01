# Self-hosting on a VPS

This runs Job Hunter on one Linux server, with HTTPS from Let's Encrypt via
Caddy. Only ports 80 and 443 are open to the internet; Postgres, the API and
the web app stay inside Docker's network.

## You need

- A Linux server with at least 2 GB of RAM (the web image builds on it),
  Intel/AMD (amd64) or ARM (arm64) - CI builds and tests both.
- Docker Engine with Compose 2.24 or newer (`docker compose version`).
- A domain or subdomain, with an `A` (and `AAAA` if you use IPv6) record
  pointing at the server.
- An SMTP account for sign-in emails - any transactional email provider.

## Install

```sh
git clone https://github.com/RichardHuang24/job-hunter.git
cd job-hunter
./scripts/setup-env.sh
```

Edit `.env`:

| Setting | Set it to |
| --- | --- |
| `DOMAIN` | your domain, e.g. `jobs.example.com` |
| `EMAIL_SERVER` | your SMTP URL, e.g. `smtp://user:password@smtp.example.com:587` - not Mailpit |
| `EMAIL_FROM` | a sender address your SMTP provider accepts |
| `AUTH_GITHUB_*`, `AUTH_GOOGLE_*` | optional; callback URL `https://<DOMAIN>/api/auth/callback/github` (or `/google`) |

`AUTH_URL` is set from `DOMAIN` for you. Keep the generated secrets:
changing `AUTH_SECRET` signs everyone out, and `POSTGRES_PASSWORD` and the
`STORAGE_*` keys are only read when the database and the file store are
first created.

Open the firewall for SSH, HTTP and HTTPS only - for example with `ufw`:

```sh
sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
```

Start it:

```sh
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

Caddy fetches the certificate on the first request to `https://<DOMAIN>`.
Check everything is up:

```sh
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml ps
docker compose exec worker python -m app.worker --check
```

## Update

```sh
git pull
./scripts/setup-env.sh    # adds any secret a newer version needs; changes nothing else
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

Database migrations run by themselves before the API and worker start.

## Files

Generated files - CV PDFs - go to the `storage` service: the
[Versity S3 Gateway](https://github.com/versity/versitygw), which keeps them
as plain files in the `storage-data` volume and speaks the S3 API to the
API and worker. Nothing outside the stack can reach it.

To keep files in Cloudflare R2, AWS S3 or another S3-compatible service
instead, set these in `.env` (the `storage` service then sits idle):

| Setting | Cloudflare R2 | AWS S3 |
| --- | --- | --- |
| `S3_ENDPOINT_URL` | `https://<account id>.r2.cloudflarestorage.com` | empty |
| `S3_REGION` | `auto` | your bucket's region, e.g. `eu-west-2` |
| `S3_BUCKET` | your bucket | your bucket |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | an R2 API token's keys | an IAM user's keys, allowed to get, put and delete objects in the bucket |

The bucket is created if it's missing and the keys allow it. Files are only
ever served through the API, to their owner, so keep the bucket private.

## Back up

The state is the database and the stored files. A nightly dump of the
database, kept off the server, is the part that matters:

```sh
docker compose exec -T db pg_dump -U jobhunter -Fc jobhunter > jobhunter-$(date +%F).dump
```

Restore into a fresh stack with `pg_restore -U jobhunter -d jobhunter --clean`.

The stored files are CV PDFs, which anyone can make again from their CV. To
keep them too, archive the `storage-data` volume:

```sh
docker run --rm -v job-hunter_storage-data:/data:ro -v "$PWD":/backup alpine \
  tar czf /backup/files-$(date +%F).tgz -C /data .
```

## Health and logs

Every long-running service has a health check - the database, the API, the
worker (its loop is still turning), the web app, the file store and Caddy. `migrate` runs
once at each start and exits:

```sh
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml ps      # look for "(healthy)"
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml logs -f web api worker
```

If the database restarts, the worker waits and carries on by itself.

Logs are JSON lines; the admin page (`/admin`, for the addresses in
`ADMIN_EMAILS`) shows AI costs, job sources' error rates and the queue; and
`SENTRY_DSN` sends errors to Sentry - see [admin.md](admin.md).
