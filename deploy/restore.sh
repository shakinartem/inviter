#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.production}"
BACKUP_DIR="${1:-}"

if [[ -z "$BACKUP_DIR" || ! -d "$BACKUP_DIR" ]]; then
  echo "Usage: $0 backups/YYYYMMDDTHHMMSSZ" >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi
if [[ ! -f "$BACKUP_DIR/postgres.dump" || ! -f "$BACKUP_DIR/telegram-sessions.tar.gz" ]]; then
  echo "Backup directory is incomplete" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml)

if [[ -f "$BACKUP_DIR/SHA256SUMS" ]]; then
  (cd "$BACKUP_DIR" && sha256sum -c SHA256SUMS)
fi

echo "Stopping application workers before restore..."
"${COMPOSE[@]}" stop backend celery_worker celery_beat || true

echo "Restoring PostgreSQL..."
cat "$BACKUP_DIR/postgres.dump" | "${COMPOSE[@]}" exec -T postgres \
  pg_restore -U "${POSTGRES_USER:-inviter}" -d "${POSTGRES_DB:-inviter}" \
  --clean --if-exists --no-owner --no-privileges

echo "Restoring Telegram sessions with runtime ownership..."
SESSION_VOLUME="${COMPOSE_PROJECT_NAME:-qualive_inviter}_telegram_sessions"
BACKEND_IMAGE="qualive-inviter-backend:${IMAGE_TAG:-local}"
docker run --rm --user root \
  -v "$SESSION_VOLUME:/data/sessions" \
  -v "$(cd "$BACKUP_DIR" && pwd):/backup:ro" \
  "$BACKEND_IMAGE" sh -c '
    rm -rf /data/sessions/* /data/sessions/.[!.]* /data/sessions/..?* 2>/dev/null || true
    tar xzf /backup/telegram-sessions.tar.gz -C /data/sessions
    chown -R app:app /data/sessions
  '

echo "Applying current migrations..."
"${COMPOSE[@]}" run --rm migrate

echo "Starting application..."
"${COMPOSE[@]}" up -d backend celery_worker celery_beat frontend caddy

echo "Restore completed. Run deploy/smoke-test.sh next."
