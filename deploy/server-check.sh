#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.production}"
export ENV_FILE
bash deploy/validate-env.sh

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

fail() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARN: $*" >&2; }

for cmd in docker curl tar sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || fail "Required command is missing: $cmd"
done

docker info >/dev/null 2>&1 || fail "Docker daemon is unavailable for the current user"
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is unavailable"
docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml config -q || fail "Production Compose configuration is invalid"

free_kb="$(df -Pk . | awk 'NR==2 {print $4}')"
free_gb=$(( free_kb / 1024 / 1024 ))
if (( free_gb < 8 )); then
  fail "Less than 8 GiB free disk space is available (${free_gb} GiB)"
elif (( free_gb < 20 )); then
  warn "Only ${free_gb} GiB free disk space is available; 20+ GiB is recommended for images, DB growth and backups"
else
  echo "Disk: ${free_gb} GiB free"
fi

mem_kb="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
mem_mb=$(( mem_kb / 1024 ))
if (( mem_mb < 1800 )); then
  fail "Less than ~2 GiB RAM is available (${mem_mb} MiB)"
elif (( mem_mb < 3800 )); then
  warn "${mem_mb} MiB RAM detected; 4+ GiB is recommended for this stack"
else
  echo "RAM: ${mem_mb} MiB"
fi

swap_kb="$(awk '/SwapTotal:/ {print $2}' /proc/meminfo)"
if (( swap_kb == 0 )); then
  warn "No swap configured. A small emergency swap file is recommended on a VPS, but it is not a substitute for RAM."
fi

if [[ -r /proc/sys/vm/overcommit_memory ]]; then
  overcommit="$(cat /proc/sys/vm/overcommit_memory)"
  if [[ "$overcommit" != "1" ]]; then
    warn "vm.overcommit_memory=$overcommit. Redis recommends 1; set it persistently before production load."
  fi
fi

if command -v getent >/dev/null 2>&1; then
  resolved="$(getent ahosts "$APP_DOMAIN" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ')"
  [[ -n "$resolved" ]] || fail "APP_DOMAIN does not resolve yet: $APP_DOMAIN"
  echo "DNS $APP_DOMAIN -> $resolved"
else
  warn "getent is unavailable; DNS resolution was not prechecked"
fi

if command -v ss >/dev/null 2>&1; then
  existing_caddy="$(docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml ps -q caddy 2>/dev/null || true)"
  if [[ -z "$existing_caddy" ]]; then
    for port in 80 443; do
      if ss -ltn "sport = :$port" 2>/dev/null | tail -n +2 | grep -q .; then
        warn "TCP port $port is already in use. Caddy cannot bind it until the existing service is stopped."
      fi
    done
  fi
fi

echo "Server deployment preflight: OK"
