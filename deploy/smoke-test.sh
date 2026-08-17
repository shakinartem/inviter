#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.production}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

BASE_URL="https://${APP_DOMAIN:?APP_DOMAIN is required}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml)

echo "Checking container status..."
"${COMPOSE[@]}" ps

echo "Checking backend health through TLS edge..."
curl --fail --silent --show-error --max-time 10 "$BASE_URL/health"
echo

echo "Checking frontend..."
curl --fail --silent --show-error --max-time 10 "$BASE_URL/" >/dev/null

echo "Checking API auth endpoint is reachable..."
curl --fail --silent --show-error --max-time 10 \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -o /dev/null \
  -w 'HTTP %{http_code}\n' \
  -X POST "$BASE_URL/api/v1/auth/jwt/login" \
  --data 'username=smoke-test-invalid@example.com&password=invalid' || true

echo "Smoke test completed. Expected auth result is 400/401 for the intentionally invalid credentials."
