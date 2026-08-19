# Production deployment — Qualive Inviter

Этот каталог — канонический self-hosted deployment path. Development `docker-compose.yml` для публичного сервера **не использовать**.

## 0. Что считается production-ready контуром

- наружу опубликованы только Caddy `80/tcp`, `443/tcp`, `443/udp`;
- Postgres, Redis, backend и frontend не имеют host ports;
- TLS выпускает/обновляет Caddy;
- public registration, FastAPI docs/OpenAPI и debug отключены;
- backend `/health/ready` проверяет **Postgres + Redis**, а `/health/live` только процесс;
- Postgres migrations выполняются отдельным one-shot service в maintenance window;
- Redis работает с `noeviction`, чтобы очередь не исчезала молча при memory pressure;
- Docker logs ограничены по размеру/числу файлов;
- Telegram `.session` хранятся в persistent volume;
- backup содержит PostgreSQL + Telegram sessions, checksums и metadata и проверяется на читаемость;
- production deploy выполняется через `deploy/deploy.sh`, а не ручным `docker compose up -d`;
- runtime версии совпадают с CI: Python 3.12 / Node 22.

## 1. Ресурсы сервера

Для текущего single-VPS контура ориентир:

- минимум для небольшого объёма: 2 vCPU / 4 GiB RAM;
- нормальный старт с запасом: 4 vCPU / 8 GiB RAM / 60–100 GiB SSD;
- свободного диска перед deploy должно быть не меньше 8 GiB; `server-check.sh` предупреждает ниже 20 GiB;
- Docker Engine + Docker Compose plugin.

Это не обещание throughput: фактическая безопасная ёмкость определяется Account Capacity/Risk Engine, Telegram limits и состоянием аккаунтов.

## 2. DNS и firewall

До первого deploy создай A/AAAA запись `APP_DOMAIN` на публичный IP сервера.

Разрешить наружу:

- SSH — лучше только с доверенных IP/VPN;
- `80/tcp`;
- `443/tcp`;
- `443/udp` — HTTP/3; можно убрать публикацию UDP 443 из compose, если он не нужен.

**Не открывать:** 5432, 6379, 8000, 5173.

Если используется внешний CDN/reverse proxy, отдельно настрой trusted proxy policy. Backend напрямую публиковать не нужно.

## 3. Размещение проекта

Рекомендуемый путь:

```bash
sudo mkdir -p /opt/qualive-inviter
sudo chown "$USER":"$USER" /opt/qualive-inviter
cd /opt/qualive-inviter
# распаковать validated release archive сюда
```

В архиве должна быть одна корневая папка `qualive-inviter/`; можно перенести её содержимое в `/opt/qualive-inviter`.

## 4. Production environment

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

Обязательно заменить:

- `APP_DOMAIN`;
- `APP_SECRET`;
- `POSTGRES_PASSWORD`;
- `REDIS_PASSWORD`.

Генерируй **три разных** секрета, например:

```bash
openssl rand -hex 48
```

`deploy/validate-env.sh` fail-closed проверяет placeholders, длину, совпадающие secrets, домен и permissions файла.

`APP_SECRET` после начала хранения encrypted connector credentials нельзя просто заменить: нужна отдельная key-rotation процедура.

Не добавляй `.env.production` в Git, backup archive, issue или чат.

## 5. Kernel/VPS preparation

Для Redis:

```bash
sudo sysctl -w vm.overcommit_memory=1
echo 'vm.overcommit_memory = 1' | sudo tee /etc/sysctl.d/99-qualive-inviter.conf
```

На небольшом VPS желательно иметь небольшой emergency swap. Swap не заменяет RAM.

Перед deploy:

```bash
bash deploy/server-check.sh
```

Он проверит Docker/Compose, production env, Compose config, RAM, disk, DNS и базовые host prerequisites.

## 6. Первый deploy

**Каноническая команда:**

```bash
bash deploy/deploy.sh
```

Скрипт:

1. выполняет server/env preflight;
2. определяет release tag (Git SHA либо timestamp для распакованного архива);
3. собирает target images;
4. поднимает/проверяет Postgres и Redis;
5. переводит приложение в maintenance window;
6. запускает `alembic upgrade head` отдельным контейнером и ждёт exit code 0;
7. только после успешной migration запускает backend/worker/beat/frontend/Caddy;
8. ждёт backend/frontend/worker health;
9. выполняет HTTPS smoke test;
10. только после полного успеха пишет `.deploy-current`.

При повторном deploy, если база уже работает, до migration автоматически создаётся verified backup текущего release.

**Не заменяй этот flow на `docker compose up -d`:** ручной запуск может пропустить обязательную migration/backup/validation последовательность.

## 7. Первый администратор

Public registration отключена. После первого успешного deploy:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml \
  exec backend python -m app.cli.create_admin --email you@example.com
```

Пароль вводится интерактивно и не попадает в shell history.

## 8. Проверка после deploy

```bash
bash deploy/smoke-test.sh
```

Проверяется:

- `https://<domain>/health/live`;
- `https://<domain>/health/ready` и доступность Postgres/Redis;
- frontend через TLS;
- HTTP → HTTPS redirect;
- docs/OpenAPI/registration закрыты;
- invalid login отклоняется;
- Postgres/Redis/backend не опубликованы на host ports;
- Celery worker healthy.

Дополнительно:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200 backend celery_worker celery_beat
```

## 9. Обновление

Распакуй/получи новый validated release и снова запусти:

```bash
bash deploy/deploy.sh
```

Предыдущий release tag сохраняется в `.deploy-previous`, текущий — в `.deploy-current`.

Важно: после schema migration **нельзя автоматически откатывать только Docker image**. Старый код может быть несовместим с новой схемой. При неуспешной migration/deploy приложение намеренно остаётся остановленным; используй pre-deploy backup и restore.

## 10. Backup

Ручной:

```bash
bash deploy/backup.sh
```

Backup содержит:

- `postgres.dump`;
- `telegram-sessions.tar.gz`;
- `SHA256SUMS`;
- `METADATA` с release tag.

Postgres dump снимается online. Для консистентного snapshot Telethon SQLite sessions backend/worker/beat кратко останавливаются, затем поднимаются через `trap` даже при ошибке snapshot.

Перед завершением backup автоматически проверяет:

- что PostgreSQL dump читается `pg_restore --list`;
- что session tar читается;
- SHA-256 checksums.

`BACKUP_RETENTION_DAYS` управляет локальной ротацией (по умолчанию 14 дней).

**Backup на том же VPS не является полноценной резервной копией.** Копируй verified backup в отдельный зашифрованный storage. Telegram session archive — credential material.

## 11. Автоматический ежедневный backup

Есть systemd templates:

- `deploy/systemd/qualive-inviter-backup.service.example`;
- `deploy/systemd/qualive-inviter-backup.timer.example`.

Если проект находится в `/opt/qualive-inviter`:

```bash
sudo cp deploy/systemd/qualive-inviter-backup.service.example /etc/systemd/system/qualive-inviter-backup.service
sudo cp deploy/systemd/qualive-inviter-backup.timer.example /etc/systemd/system/qualive-inviter-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now qualive-inviter-backup.timer
systemctl list-timers | grep qualive-inviter
```

Если путь другой — сначала измени `WorkingDirectory`, `Environment` и `ExecStart` в service unit.

## 12. Restore

Restore деструктивен и требует явного подтверждения:

```bash
RESTORE_CONFIRM=YES bash deploy/restore.sh backups/20260820T010203Z
```

Restore:

1. валидирует environment;
2. требует checksums + metadata;
3. проверяет project/database identity;
4. останавливает Caddy/backend/workers;
5. восстанавливает PostgreSQL с `--exit-on-error`;
6. восстанавливает Telegram sessions с правильным ownership;
7. повторно применяет migrations текущего release;
8. поднимает stack;
9. запускает HTTPS smoke test.

При ошибке в процессе application намеренно остаётся stopped, чтобы не обслуживать partial restore.

Cross-project restore запрещён по умолчанию. Для сознательного переноса можно использовать `ALLOW_CROSS_PROJECT_RESTORE=true`.

## 13. Telegram sessions и concurrency

Текущий production contour — **single-VPS**, shared persistent `.session` storage.

Safe defaults:

```env
WEB_CONCURRENCY=1
CELERY_CONCURRENCY=1
```

Не увеличивай их ради throughput без отдельной проверки session-access pattern. Telethon session state — SQLite credential/state, и простое горизонтальное масштабирование нескольких nodes на общий volume не является безопасной архитектурой.

Для multi-node deployment нужен отдельный account session lease/worker-affinity слой. До его появления масштабируй throughput количеством корректно управляемых account capacity, а не числом процессов.

## 14. Postgres/Redis

- Postgres — source of truth;
- Redis — queue/cache/rate-state, но `noeviction` включён специально: лучше получить явную ошибку memory pressure, чем молча потерять queued keys;
- backend использует bounded SQL pool + `pool_pre_ping`;
- Redis connections имеют connect/read timeout и periodic health checks.

Если Redis начинает упираться в память — увеличь RAM/исправь workload, а не включай eviction policy для Celery broker.

## 15. Logs

Compose ограничивает Docker JSON logs через:

```env
DOCKER_LOG_MAX_SIZE=20m
DOCKER_LOG_MAX_FILES=5
```

Приложение в production пишет structured JSON (`LOG_JSON=true`). Для длительной эксплуатации лучше отправлять stdout/stderr в централизованное хранилище логов/метрик, но локальный диск больше не должен бесконтрольно заполняться Docker logs.

## 16. Что мониторить

Минимум:

- backend `/health/ready`;
- container restarts;
- Postgres disk/volume growth;
- Redis memory;
- backup timer success;
- свободный disk;
- Caddy certificate renewal;
- Celery queue depth;
- Telegram account quarantine/cooldown/risk;
- `campaign_preflight_decisions` / SLA calibration health.

## 17. Production boundaries

Этот release закрывает single-server deployment. Он **не заявляет** безопасный active-active multi-node Telethon execution: до session leasing держи один VPS/runtime ownership domain.

Следующий инфраструктурный уровень для масштабирования — account session leasing + worker affinity, external secrets/KMS и отдельный analytical warehouse. Они не нужны для корректного первого production deploy на одном сервере.
