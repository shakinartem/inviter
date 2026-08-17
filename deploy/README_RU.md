# Production deployment — Qualive Inviter

Этот контур предназначен для публичного сервера. Development `docker-compose.yml` оставлен отдельно.

## Что меняется относительно dev

- Postgres и Redis не публикуют порты наружу.
- Redis защищён паролем и доступен только во внутренней Docker-сети.
- Backend запускается без `--reload`, несколькими Uvicorn workers.
- Frontend собирается один раз и раздаётся Nginx.
- Caddy принимает 80/443 и автоматически получает/обновляет TLS-сертификат.
- Public registration и FastAPI docs по умолчанию отключены.
- Telegram `.session` лежат в отдельном persistent volume.
- Alembic migration выполняется до старта backend.
- Есть backup/restore базы и Telegram sessions.

## 1. Подготовка сервера

Нужны Docker Engine + Docker Compose plugin и открытые TCP 80/443 (для HTTP/HTTPS) и UDP 443 (HTTP/3, необязательно, но compose публикует его).

В DNS создай A/AAAA запись домена на сервер, например `inviter.example.com`. До запуска Caddy домен уже должен резолвиться на публичный IP сервера, иначе автоматическая выдача TLS-сертификата не пройдёт.

Для Redis на Linux рекомендуется включить memory overcommit:

```bash
sudo sysctl -w vm.overcommit_memory=1
echo 'vm.overcommit_memory = 1' | sudo tee /etc/sysctl.d/99-qualive-inviter.conf
```

На небольшом VPS также проверь наличие swap, но не воспринимай swap как замену достаточной RAM.

## 2. Environment

```bash
cp .env.production.example .env.production
```

Обязательно замени:

- `APP_DOMAIN`
- `APP_SECRET`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`

Удобно генерировать секреты так:

```bash
openssl rand -hex 48
```

Production backend намеренно не стартует с дефолтными/слишком короткими секретами. `APP_SECRET` нельзя менять после начала использования encrypted connector credentials без заранее спланированной ротации.

## 3. Первый запуск

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

Compose сначала поднимет Postgres/Redis, применит `alembic upgrade head`, затем backend/workers/frontend/Caddy.

Проверка:

```bash
bash deploy/smoke-test.sh
```

## 4. Создать первого администратора

Public registration в production отключена. Создай администратора интерактивно:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml \
  run --rm backend python -m app.cli.create_admin --email you@example.com
```

Пароль вводится интерактивно и не попадает в shell history.

## 5. Обновление

Перед обновлением сделай backup:

```bash
bash deploy/backup.sh
```

После получения новой версии:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
bash deploy/smoke-test.sh
```

Migrate service применит новые Alembic migrations до старта backend.

## 6. Backup

```bash
bash deploy/backup.sh
```

Получишь каталог `backups/<UTC timestamp>/` с:

- `postgres.dump`
- `telegram-sessions.tar.gz`
- `SHA256SUMS`
- `METADATA`

PostgreSQL dump снимается online. Для Telegram `.session` backup **кратко останавливает backend/worker/beat**, потому что Telethon session — SQLite-файл и копировать его во время записи небезопасно. Скрипт использует `trap` и поднимает процессы обратно даже при ошибке архивации.

Redis отдельно не сохраняется: он используется как cache/queue/rate-state, а не как основной source of truth.

Копируй backup на отдельное хранилище. Backup, лежащий только на том же VPS, не считается резервной копией. Для production имеет смысл дополнительно шифровать backup перед отправкой в object storage, потому что Telegram session-файлы являются чувствительными credentials.

## 7. Restore

```bash
bash deploy/restore.sh backups/20260818T010203Z
bash deploy/smoke-test.sh
```

Restore останавливает backend/workers, восстанавливает Postgres + Telegram sessions, возвращает session-файлам ownership runtime-пользователя, применяет текущие migrations и запускает приложение снова.

## 8. Сеть

Наружу публикуются только:

- `80/tcp`
- `443/tcp`
- `443/udp`

Postgres `5432`, Redis `6379`, backend `8000` и frontend `80` доступны только внутри Docker networks.

## 9. Важные production-параметры

- `APP_ALLOW_REGISTRATION=false`
- `APP_DOCS_ENABLED=false`
- `APP_DEBUG=false`
- `LOG_JSON=true`
- `WEB_CONCURRENCY` — число Uvicorn workers
- `CELERY_CONCURRENCY` — worker concurrency
- `SESSIONS_DIR=/data/sessions`

Не увеличивай concurrency только ради throughput: messaging connectors имеют platform/rate/account constraints, а безопасная пропускная способность определяется scheduler/account health, а не количеством процессов.

## 10. Что проверить после деплоя

1. `https://<domain>/health` возвращает `status=ok`.
2. UI открывается через HTTPS.
3. `/api/v1/auth/register` отсутствует при `APP_ALLOW_REGISTRATION=false`.
4. `/docs` недоступен при `APP_DOCS_ENABLED=false`.
5. Admin login работает.
6. Telegram account/session переживает `docker compose down` → `up -d`.
7. Worker и Beat не перезапускаются циклически.
8. `bash deploy/backup.sh` создаёт валидные checksums и после snapshot процессы снова подняты.
9. `docker compose ... ps` показывает healthy backend/frontend/Postgres/Redis.

## 11. Firewall

На сервере достаточно разрешить SSH с доверенных адресов и web traffic 80/443. Не открывай Postgres/Redis/8000/5173 наружу.

Если сервер находится за дополнительным reverse proxy/CDN, отдельно настрой trusted proxy/IP policy; не публикуй backend напрямую ради обхода Caddy.

## 12. Secrets

`.env.production` игнорируется Git и не должен попадать в архивы, тикеты или чаты. Для команды production secrets лучше вынести в отдельный password/secrets manager; Docker Compose env-файл — стартовый self-hosted вариант, не конечный enterprise secret-management слой.

`telegram_sessions` volume также содержит секретный материал и должен рассматриваться как credentials store: ограничь доступ к Docker socket/root и не копируй volume в небезопасные места.
