#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.production}"
export ENV_FILE
bash deploy/validate-env.sh

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

BACKUP_ROOT="${BACKUP_ROOT:-backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
[[ "$BACKUP_RETENTION_DAYS" =~ ^[0-9]+$ ]] || { echo "BACKUP_RETENTION_DAYS must be an integer" >&2; exit 1; }
(( BACKUP_RETENTION_DAYS >= 1 )) || { echo "BACKUP_RETENTION_DAYS must be >= 1" >&2; exit 1; }

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

echo "[1/5] Dumping PostgreSQL online..."
"${COMPOSE[@]}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-inviter}" -d "${POSTGRES_DB:-inviter}" -Fc \
  > "$DEST/postgres.dump"

echo "[2/5] Pausing Telegram clients for a consistent session snapshot..."
"${COMPOSE[@]}" stop backend celery_worker celery_beat
APP_PAUSED=1

echo "[3/5] Archiving Telegram sessions..."
SESSION_VOLUME="${COMPOSE_PROJECT_NAME:-qualive_inviter}_telegram_sessions"
docker run --rm \
  -v "$SESSION_VOLUME:/data:ro" \
  -v "$(cd "$DEST" && pwd):/backup" \
  alpine:3.20 sh -c 'cd /data && tar czf /backup/telegram-sessions.tar.gz .'

resume_app
APP_PAUSED=0
trap - EXIT

echo "[4/5] Verifying backup readability and checksums..."
cat "$DEST/postgres.dump" | "${COMPOSE[@]}" exec -T postgres pg_restore --list >/dev/null
tar tzf "$DEST/telegram-sessions.tar.gz" >/dev/null
(
  cd "$DEST"
  sha256sum postgres.dump telegram-sessions.tar.gz > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)

release_tag="unknown"
if [[ -f .deploy-current ]]; then
  release_tag="$(tr -d '\r\n' < .deploy-current)"
fi
printf 'created_at=%s\nproject=%s\npostgres_db=%s\nsession_snapshot=application_paused\nrelease_tag=%s\n' \
  "$STAMP" "${COMPOSE_PROJECT_NAME:-qualive_inviter}" "${POSTGRES_DB:-inviter}" "$release_tag" \
  > "$DEST/METADATA"

echo "[5/5] Pruning local backups older than ${BACKUP_RETENTION_DAYS} days..."
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
  -regextype posix-extended -regex '.*/[0-9]{8}T[0-9]{6}Z' \
  -mtime "+$BACKUP_RETENTION_DAYS" -print -exec rm -rf -- {} +

echo "Backup created and verified: $DEST"
