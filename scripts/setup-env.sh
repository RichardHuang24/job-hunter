#!/bin/sh
# Creates .env from .env.example with fresh random secrets. Run it once, from
# anywhere in the repo - and again after an update: on an existing .env it
# only adds secrets a newer version needs, and changes nothing else.
set -eu
cd "$(dirname "$0")/.."

SECRETS="AUTH_SECRET BACKEND_JWT_SECRET POSTGRES_PASSWORD STORAGE_ACCESS_KEY STORAGE_SECRET_KEY"

random_hex() {  # $1 bytes
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$1"
  else
    python3 -c "import secrets, sys; print(secrets.token_hex(int(sys.argv[1])))" "$1"
  fi
}

value_for() {
  case "$1" in
    STORAGE_ACCESS_KEY) echo "jobhunter$(random_hex 8)" ;;  # an S3 access key id: short, no secret
    *) random_hex 32 ;;
  esac
}

umask 077
if [ -e .env ]; then
  added=""
  for name in $SECRETS; do
    if ! grep -q "^$name=." .env; then
      if grep -q "^$name=" .env; then
        sed -i.bak "s/^$name=.*/$name=$(value_for "$name")/" .env && rm -f .env.bak
      else
        printf '%s=%s\n' "$name" "$(value_for "$name")" >> .env
      fi
      added="$added $name"
    fi
  done
  if [ -n "$added" ]; then
    echo "Added to .env:$added"
  else
    echo ".env already has every secret - leaving it as it is."
  fi
  exit 0
fi

cp .env.example .env
for name in $SECRETS; do
  sed -i.bak "s/^$name=.*/$name=$(value_for "$name")/" .env && rm -f .env.bak
done
echo "Created .env with new secrets. Next: docker compose up --build"
