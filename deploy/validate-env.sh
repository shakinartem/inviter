#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.production}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

warn() {
  echo "WARN: $*" >&2
}

[[ -f "$ENV_FILE" ]] || fail "Missing $ENV_FILE. Copy .env.production.example and fill real values first."

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${APP_DOMAIN:?APP_DOMAIN is required}"
: "${APP_SECRET:?APP_SECRET is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${REDIS_PASSWORD:?REDIS_PASSWORD is required}"

case "${APP_DOMAIN,,}" in
  localhost|*.localhost|127.0.0.1|example.com|*.example.com)
    fail "APP_DOMAIN must be a real production DNS name, not $APP_DOMAIN"
    ;;
esac
[[ "$APP_DOMAIN" != *"://"* ]] || fail "APP_DOMAIN must not include a URL scheme"
[[ "$APP_DOMAIN" != */* ]] || fail "APP_DOMAIN must not include a path"
[[ "$APP_DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]] || fail "APP_DOMAIN contains unsupported characters"
[[ "$APP_DOMAIN" == *.* ]] || fail "APP_DOMAIN must be a fully qualified DNS name"

placeholder_re='(^|[_-])(change[_-]?me|changeme|example|placeholder|default)([_-]|$)'
for name in APP_SECRET POSTGRES_PASSWORD REDIS_PASSWORD; do
  value="${!name}"
  [[ ! "${value,,}" =~ $placeholder_re ]] || fail "$name still looks like a template placeholder"
done

(( ${#APP_SECRET} >= 48 )) || fail "APP_SECRET must contain at least 48 characters"
(( ${#POSTGRES_PASSWORD} >= 20 )) || fail "POSTGRES_PASSWORD must contain at least 20 characters"
(( ${#REDIS_PASSWORD} >= 20 )) || fail "REDIS_PASSWORD must contain at least 20 characters"

[[ "$APP_SECRET" != "$POSTGRES_PASSWORD" ]] || fail "APP_SECRET and POSTGRES_PASSWORD must be different"
[[ "$APP_SECRET" != "$REDIS_PASSWORD" ]] || fail "APP_SECRET and REDIS_PASSWORD must be different"
[[ "$POSTGRES_PASSWORD" != "$REDIS_PASSWORD" ]] || fail "POSTGRES_PASSWORD and REDIS_PASSWORD must be different"

for name in WEB_CONCURRENCY CELERY_CONCURRENCY DB_POOL_SIZE DB_MAX_OVERFLOW; do
  value="${!name:-}"
  [[ -z "$value" || "$value" =~ ^[0-9]+$ ]] || fail "$name must be an integer"
done

WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-1}"
(( WEB_CONCURRENCY >= 1 && WEB_CONCURRENCY <= 16 )) || fail "WEB_CONCURRENCY must be between 1 and 16"
(( CELERY_CONCURRENCY >= 1 && CELERY_CONCURRENCY <= 32 )) || fail "CELERY_CONCURRENCY must be between 1 and 32"

if (( WEB_CONCURRENCY > 1 || CELERY_CONCURRENCY > 1 )); then
  warn "Telegram .session files are shared across backend/worker processes. Keep concurrency at 1 until account session leasing is implemented, unless you have independently validated your session-access pattern."
fi

if mode="$(stat -c '%a' "$ENV_FILE" 2>/dev/null)"; then
  other_digit="${mode: -1}"
  if (( other_digit > 0 )); then
    fail "$ENV_FILE is accessible by other users (mode $mode). Run: chmod 600 $ENV_FILE"
  fi
  group_digit="${mode: -2:1}"
  if (( group_digit > 0 )); then
    warn "$ENV_FILE is group-accessible (mode $mode). 600 is recommended on a single-admin VPS."
  fi
fi

if [[ "${APP_DEBUG:-false}" == "true" || "${APP_DEBUG:-false}" == "1" ]]; then
  fail "APP_DEBUG must be false in production"
fi
if [[ "${APP_ALLOW_REGISTRATION:-false}" == "true" || "${APP_ALLOW_REGISTRATION:-false}" == "1" ]]; then
  warn "APP_ALLOW_REGISTRATION is ignored by the hardened production Compose and remains disabled."
fi
if [[ "${APP_DOCS_ENABLED:-false}" == "true" || "${APP_DOCS_ENABLED:-false}" == "1" ]]; then
  warn "APP_DOCS_ENABLED is ignored by the hardened production Compose and remains disabled."
fi

echo "Production environment validation: OK"
