# Self-hosting on a VPS

This runs Job Hunter on one Linux server, with HTTPS from Let's Encrypt via
Caddy. Only ports 80 and 443 are open to the internet; Postgres, the API and
the web app stay inside Docker's network.

## You need

- A Linux server with at least 2 GB of RAM (the web image builds on it).
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

`AUTH_URL` is set from `DOMAIN` for you. Keep the three generated secrets;
changing `AUTH_SECRET` signs everyone out, and `POSTGRES_PASSWORD` is only read
when the database is first created.

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
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

Database migrations run by themselves before the API and worker start.

## Back up

The database is the only state. A nightly dump, kept off the server, is
enough:

```sh
docker compose exec -T db pg_dump -U jobhunter -Fc jobhunter > jobhunter-$(date +%F).dump
```

Restore into a fresh stack with `pg_restore -U jobhunter -d jobhunter --clean`.

## Logs

```sh
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml logs -f web api worker
```
