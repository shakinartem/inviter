#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.production}"
BACKUP_ROOT="${BACKUP_ROOT:-backups}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml)
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$BACKUP_ROOT/$STAMP"
mkdir -p "$DEST"

APP_PAUSED=0
resume_app() {
  if [[ "$APP_PAUSED" == "1" ]]; then
    echo "Resuming backend/workers..."
    "${COMPOSE[@]}" up -d backend celery_worker celery_beat >/dev/null || true
  fi
}
trap resume_app EXIT

echo "[1/4] Dumping PostgreSQL online..."
"${COMPOSE[@]}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-inviter}" -d "${POSTGRES_DB:-inviter}" -Fc \
  > "$DEST/postgres.dump"

echo "[2/4] Pausing Telegram clients for a consistent session snapshot..."
"${COMPOSE[@]}" stop backend celery_worker celery_beat
APP_PAUSED=1

echo "[3/4] Archiving Telegram sessions..."
SESSION_VOLUME="${COMPOSE_PROJECT_NAME:-qualive_inviter}_telegram_sessions"
docker run --rm \
  -v "$SESSION_VOLUME:/data:ro" \
  -v "$(cd "$DEST" && pwd):/backup" \
  alpine:3.20 sh -c 'cd /data && tar czf /backup/telegram-sessions.tar.gz .'

resume_app
APP_PAUSED=0
trap - EXIT

echo "[4/4] Writing checksums and metadata..."
(
  cd "$DEST"
  sha256sum postgres.dump telegram-sessions.tar.gz > SHA256SUMS
)
printf 'created_at=%s\nproject=%s\npostgres_db=%s\nsession_snapshot=application_paused\n' \
  "$STAMP" "${COMPOSE_PROJECT_NAME:-qualive_inviter}" "${POSTGRES_DB:-inviter}" \
  > "$DEST/METADATA"

echo "Backup created: $DEST"
