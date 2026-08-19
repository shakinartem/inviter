#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.production}"
BACKUP_BEFORE_DEPLOY="${BACKUP_BEFORE_DEPLOY:-true}"
SMOKE_RETRIES="${SMOKE_RETRIES:-30}"

export ENV_FILE
bash deploy/validate-env.sh

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml)

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  RELEASE_TAG="${RELEASE_TAG:-$(git rev-parse --short=12 HEAD)}"
else
  RELEASE_TAG="${RELEASE_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
fi

CURRENT_TAG=""
if [[ -f .deploy-current ]]; then
  CURRENT_TAG="$(tr -d '\r\n' < .deploy-current)"
fi
if [[ -z "$CURRENT_TAG" ]]; then
  existing_backend_id="$("${COMPOSE[@]}" ps -q backend 2>/dev/null || true)"
  if [[ -n "$existing_backend_id" ]]; then
    current_image="$(docker inspect -f '{{.Config.Image}}' "$existing_backend_id" 2>/dev/null || true)"
    [[ "$current_image" == qualive-inviter-backend:* ]] && CURRENT_TAG="${current_image##*:}"
  fi
fi

wait_for_migration() {
  local id status code
  id="$(IMAGE_TAG="$RELEASE_TAG" "${COMPOSE[@]}" ps -aq migrate)"
  [[ -n "$id" ]] || { echo "Migration container was not created" >&2; return 1; }
  for _ in $(seq 1 120); do
    status="$(docker inspect -f '{{.State.Status}}' "$id")"
    if [[ "$status" == "exited" ]]; then
      code="$(docker inspect -f '{{.State.ExitCode}}' "$id")"
      if [[ "$code" == "0" ]]; then
        return 0
      fi
      docker logs "$id" >&2 || true
      echo "Migration failed with exit code $code" >&2
      return 1
    fi
    sleep 1
  done
  docker logs "$id" >&2 || true
  echo "Migration did not finish within 120 seconds" >&2
  return 1
}

wait_for_health() {
  local service="$1" id status
  id="$(IMAGE_TAG="$RELEASE_TAG" "${COMPOSE[@]}" ps -q "$service")"
  [[ -n "$id" ]] || { echo "$service container is missing" >&2; return 1; }
  for _ in $(seq 1 60); do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id")"
    if [[ "$status" == "healthy" || "$status" == "running" ]]; then
      return 0
    fi
    if [[ "$status" == "unhealthy" || "$status" == "exited" || "$status" == "dead" ]]; then
      docker logs "$id" >&2 || true
      echo "$service failed health check: $status" >&2
      return 1
    fi
    sleep 2
  done
  docker logs "$id" >&2 || true
  echo "$service did not become healthy" >&2
  return 1
}

echo "Current release: ${CURRENT_TAG:-none}"
echo "Target release:  $RELEASE_TAG"
IMAGE_TAG="$RELEASE_TAG" "${COMPOSE[@]}" config -q

postgres_id="$("${COMPOSE[@]}" ps -q postgres 2>/dev/null || true)"
if [[ "$BACKUP_BEFORE_DEPLOY" == "true" && -n "$postgres_id" && "$(docker inspect -f '{{.State.Running}}' "$postgres_id" 2>/dev/null || true)" == "true" ]]; then
  echo "Creating pre-deploy backup from current release..."
  if [[ -n "$CURRENT_TAG" ]]; then
    IMAGE_TAG="$CURRENT_TAG" bash deploy/backup.sh
  else
    bash deploy/backup.sh
  fi
fi

echo "Building target production images while current release is still serving..."
IMAGE_TAG="$RELEASE_TAG" "${COMPOSE[@]}" build --pull backend frontend

echo "Starting/validating state services..."
IMAGE_TAG="$RELEASE_TAG" "${COMPOSE[@]}" up -d postgres redis
wait_for_health postgres
wait_for_health redis

echo "Entering maintenance window before schema migration..."
IMAGE_TAG="${CURRENT_TAG:-$RELEASE_TAG}" "${COMPOSE[@]}" stop caddy backend celery_worker celery_beat || true

migration_started=1
failed_deploy() {
  if [[ "${migration_started:-0}" == "1" ]]; then
    echo "Deployment failed after entering the migration window." >&2
    echo "Application remains stopped intentionally; do not restart the previous release blindly after a schema change." >&2
    echo "Inspect migration/container logs. If needed, restore the pre-deploy backup with RESTORE_CONFIRM=YES deploy/restore.sh <backup-dir>." >&2
  fi
}
trap failed_deploy ERR

echo "Running database migrations as a dedicated one-shot service..."
IMAGE_TAG="$RELEASE_TAG" "${COMPOSE[@]}" up -d --force-recreate migrate
wait_for_migration

echo "Starting target application services..."
IMAGE_TAG="$RELEASE_TAG" "${COMPOSE[@]}" up -d --remove-orphans backend celery_worker celery_beat frontend caddy
wait_for_health backend
wait_for_health frontend
wait_for_health celery_worker

export SMOKE_RETRIES
bash deploy/smoke-test.sh

trap - ERR
if [[ -n "$CURRENT_TAG" && "$CURRENT_TAG" != "$RELEASE_TAG" ]]; then
  printf '%s\n' "$CURRENT_TAG" > .deploy-previous
fi
printf '%s\n' "$RELEASE_TAG" > .deploy-current

echo "Deployment successful. Release: $RELEASE_TAG"
IMAGE_TAG="$RELEASE_TAG" "${COMPOSE[@]}" ps
