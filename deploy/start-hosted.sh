#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  host=${1:-}
  if [[ ! "$host" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ || "$host" != *.* ]]; then
    echo "Usage: bash deploy/start-hosted.sh your.public.hostname" >&2
    exit 2
  fi
  umask 077
  tmp=$(mktemp .env.XXXXXX)
  trap 'rm -f -- "$tmp"' EXIT
  {
    echo "PUBLIC_HOST=$host"
    for key in DJANGO_SECRET_KEY POSTGRES_PASSWORD WORKER_INGEST_TOKEN; do
      echo "$key=$(openssl rand -hex 32)"
    done
  } > "$tmp"
  ln "$tmp" .env
fi

compose=(docker compose --env-file .env -f deploy/docker-compose.yml -f deploy/compose.hosted.yml)
"${compose[@]}" config --quiet
"${compose[@]}" up --build -d
"${compose[@]}" ps
