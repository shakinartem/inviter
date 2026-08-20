#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.production}"
SMOKE_RETRIES="${SMOKE_RETRIES:-30}"
SMOKE_DELAY_SECONDS="${SMOKE_DELAY_SECONDS:-2}"

export ENV_FILE
bash deploy/validate-env.sh

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

BASE_URL="https://${APP_DOMAIN:?APP_DOMAIN is required}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml)

retry_https() {
  local path="$1" output=""
  for _ in $(seq 1 "$SMOKE_RETRIES"); do
    if output="$(curl --proto '=https' --tlsv1.2 --fail --silent --show-error --max-time 10 "$BASE_URL$path" 2>/dev/null)"; then
      printf '%s' "$output"
      return 0
    fi
    sleep "$SMOKE_DELAY_SECONDS"
  done
  echo "HTTPS smoke check failed: $BASE_URL$path" >&2
  return 1
}

echo "Checking container status..."
"${COMPOSE[@]}" ps

echo "Checking backend liveness through TLS edge..."
live="$(retry_https /health/live)"
[[ "$live" == *'"status":"ok"'* || "$live" == *'"status": "ok"'* ]] || { echo "Unexpected liveness payload: $live" >&2; exit 1; }

echo "Checking dependency-aware readiness through TLS edge..."
ready="$(retry_https /health/ready)"
[[ "$ready" == *'"postgres":"ok"'* || "$ready" == *'"postgres": "ok"'* ]] || { echo "Postgres not ready: $ready" >&2; exit 1; }
[[ "$ready" == *'"redis":"ok"'* || "$ready" == *'"redis": "ok"'* ]] || { echo "Redis not ready: $ready" >&2; exit 1; }

echo "Checking frontend..."
retry_https / >/dev/null

echo "Checking HTTP redirects to HTTPS..."
http_code="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 "http://${APP_DOMAIN}/")"
[[ "$http_code" =~ ^30[1278]$ ]] || { echo "Expected HTTP→HTTPS redirect, got $http_code" >&2; exit 1; }

echo "Checking docs and public registration remain closed..."
for path in /docs /openapi.json /api/v1/auth/register; do
  code="$(curl --proto '=https' --tlsv1.2 --silent --output /dev/null --write-out '%{http_code}' --max-time 10 "$BASE_URL$path")"
  [[ "$code" == "404" ]] || { echo "$path unexpectedly returned HTTP $code" >&2; exit 1; }
done

echo "Checking invalid authentication is rejected..."
auth_code="$(curl --proto '=https' --tlsv1.2 --silent --output /dev/null --write-out '%{http_code}' --max-time 10 \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -X POST "$BASE_URL/api/v1/auth/jwt/login" \
  --data 'username=smoke-test-invalid@example.invalid&password=invalid')"
[[ "$auth_code" == "400" || "$auth_code" == "401" ]] || { echo "Unexpected invalid-login status: $auth_code" >&2; exit 1; }

echo "Checking internal state services are not published..."
[[ -z "$("${COMPOSE[@]}" port postgres 5432 2>/dev/null || true)" ]] || { echo "Postgres port is published" >&2; exit 1; }
[[ -z "$("${COMPOSE[@]}" port redis 6379 2>/dev/null || true)" ]] || { echo "Redis port is published" >&2; exit 1; }
[[ -z "$("${COMPOSE[@]}" port backend 8000 2>/dev/null || true)" ]] || { echo "Backend port is published" >&2; exit 1; }

echo "Checking worker health when available..."
worker_id="$("${COMPOSE[@]}" ps -q celery_worker 2>/dev/null || true)"
if [[ -n "$worker_id" ]]; then
  worker_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$worker_id")"
  [[ "$worker_health" == "healthy" || "$worker_health" == "running" ]] || { docker logs "$worker_id" >&2 || true; echo "Worker health: $worker_health" >&2; exit 1; }
fi

echo "Smoke test completed successfully."
