#!/bin/sh
# Creates .env from .env.example with fresh random secrets. Run once, from
# anywhere in the repo. Leaves an existing .env alone.
set -eu
cd "$(dirname "$0")/.."

if [ -e .env ]; then
  echo ".env already exists - leaving it as it is."
  exit 0
fi

secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python3 -c "import secrets; print(secrets.token_hex(32))"
  fi
}

umask 077
sed -e "s/^AUTH_SECRET=.*/AUTH_SECRET=$(secret)/" \
    -e "s/^BACKEND_JWT_SECRET=.*/BACKEND_JWT_SECRET=$(secret)/" \
    -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(secret)/" \
    .env.example > .env
echo "Created .env with new secrets. Next: docker compose up --build"
