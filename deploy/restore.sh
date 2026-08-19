#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.production}"
BACKUP_DIR="${1:-}"
RESTORE_CONFIRM="${RESTORE_CONFIRM:-}"

[[ -n "$BACKUP_DIR" && -d "$BACKUP_DIR" ]] || { echo "Usage: RESTORE_CONFIRM=YES $0 backups/YYYYMMDDTHHMMSSZ" >&2; exit 1; }
[[ "$RESTORE_CONFIRM" == "YES" ]] || { echo "Restore is destructive. Re-run with RESTORE_CONFIRM=YES" >&2; exit 1; }

export ENV_FILE
bash deploy/validate-env.sh

for required in postgres.dump telegram-sessions.tar.gz SHA256SUMS METADATA; do
  [[ -f "$BACKUP_DIR/$required" ]] || { echo "Backup is incomplete: missing $required" >&2; exit 1; }
done

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml)

(cd "$BACKUP_DIR" && sha256sum -c SHA256SUMS)
tar tzf "$BACKUP_DIR/telegram-sessions.tar.gz" >/dev/null

backup_project="$(sed -n 's/^project=//p' "$BACKUP_DIR/METADATA" | head -n1)"
backup_db="$(sed -n 's/^postgres_db=//p' "$BACKUP_DIR/METADATA" | head -n1)"
if [[ "${ALLOW_CROSS_PROJECT_RESTORE:-false}" != "true" ]]; then
  [[ "$backup_project" == "${COMPOSE_PROJECT_NAME:-qualive_inviter}" ]] || { echo "Backup project mismatch: $backup_project" >&2; exit 1; }
  [[ "$backup_db" == "${POSTGRES_DB:-inviter}" ]] || { echo "Backup database mismatch: $backup_db" >&2; exit 1; }
fi

release_tag=""
if [[ -f .deploy-current ]]; then
  release_tag="$(tr -d '\r\n' < .deploy-current)"
fi
if [[ -z "$release_tag" ]]; then
  backend_id="$("${COMPOSE[@]}" ps -q backend 2>/dev/null || true)"
  if [[ -n "$backend_id" ]]; then
    image="$(docker inspect -f '{{.Config.Image}}' "$backend_id" 2>/dev/null || true)"
    release_tag="${image##*:}"
  fi
fi
[[ -n "$release_tag" ]] || { echo "Cannot determine deployed backend release tag. Set RELEASE_TAG explicitly." >&2; exit 1; }
release_tag="${RELEASE_TAG:-$release_tag}"
export IMAGE_TAG="$release_tag"

echo "Stopping public/application services before destructive restore..."
IMAGE_TAG="$IMAGE_TAG" "${COMPOSE[@]}" stop caddy backend celery_worker celery_beat || true

cleanup_on_failure() {
  echo "Restore failed; application remains stopped to avoid serving a partially restored state." >&2
}
trap cleanup_on_failure ERR

echo "Ensuring PostgreSQL and Redis are available..."
IMAGE_TAG="$IMAGE_TAG" "${COMPOSE[@]}" up -d postgres redis

echo "Verifying PostgreSQL dump format..."
cat "$BACKUP_DIR/postgres.dump" | IMAGE_TAG="$IMAGE_TAG" "${COMPOSE[@]}" exec -T postgres pg_restore --list >/dev/null

echo "Restoring PostgreSQL..."
cat "$BACKUP_DIR/postgres.dump" | IMAGE_TAG="$IMAGE_TAG" "${COMPOSE[@]}" exec -T postgres \
  pg_restore -U "${POSTGRES_USER:-inviter}" -d "${POSTGRES_DB:-inviter}" \
  --clean --if-exists --no-owner --no-privileges --exit-on-error

echo "Restoring Telegram sessions with runtime ownership..."
SESSION_VOLUME="${COMPOSE_PROJECT_NAME:-qualive_inviter}_telegram_sessions"
BACKEND_IMAGE="qualive-inviter-backend:${IMAGE_TAG}"
docker image inspect "$BACKEND_IMAGE" >/dev/null 2>&1 || { echo "Missing deployed image $BACKEND_IMAGE" >&2; exit 1; }
docker run --rm --user root \
  -v "$SESSION_VOLUME:/data/sessions" \
  -v "$(cd "$BACKUP_DIR" && pwd):/backup:ro" \
  "$BACKEND_IMAGE" sh -c '
    rm -rf /data/sessions/* /data/sessions/.[!.]* /data/sessions/..?* 2>/dev/null || true
    tar xzf /backup/telegram-sessions.tar.gz -C /data/sessions
    chown -R app:app /data/sessions
  '

echo "Applying current migrations..."
IMAGE_TAG="$IMAGE_TAG" "${COMPOSE[@]}" up -d --force-recreate migrate
migrate_id="$(IMAGE_TAG="$IMAGE_TAG" "${COMPOSE[@]}" ps -aq migrate)"
[[ -n "$migrate_id" ]] || { echo "Migration container missing" >&2; exit 1; }
for _ in $(seq 1 120); do
  state="$(docker inspect -f '{{.State.Status}}' "$migrate_id")"
  if [[ "$state" == "exited" ]]; then
    code="$(docker inspect -f '{{.State.ExitCode}}' "$migrate_id")"
    [[ "$code" == "0" ]] || { docker logs "$migrate_id" >&2 || true; exit 1; }
    break
  fi
  sleep 1
done
[[ "$(docker inspect -f '{{.State.Status}}' "$migrate_id")" == "exited" ]] || { echo "Migration timed out" >&2; exit 1; }

echo "Starting application..."
IMAGE_TAG="$IMAGE_TAG" "${COMPOSE[@]}" up -d --remove-orphans backend celery_worker celery_beat frontend caddy
trap - ERR

export SMOKE_RETRIES="${SMOKE_RETRIES:-30}"
bash deploy/smoke-test.sh

echo "Restore completed and smoke test passed. Release: $IMAGE_TAG"
