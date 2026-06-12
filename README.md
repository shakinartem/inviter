# Inviter

Self-hosted Telegram inviter with accounts, proxies, campaigns, parser and admin settings.

## Settings

- `GET /api/v1/settings/` returns the singleton site settings row and creates it on first access.
- `PUT /api/v1/settings/` updates site name, language, help text and system config.
- `POST /api/v1/settings/logo` uploads the site logo.
- `DELETE /api/v1/settings/logo` removes the current logo.

## Branding

- Logo files are stored under `backend/uploads/logo/` at runtime.
- The backend serves uploaded files from `/uploads`.
- Logo uploads are limited to PNG, JPG, JPEG and WEBP files with a 5 MB maximum size.
- Logo changes are restricted to authenticated superusers.

## Language

- The UI supports `ru` and `en`.
- The selected locale is persisted in `localStorage`.
- The sidebar language switcher reloads the app so translated labels refresh immediately.

## Help

- The `/help` page renders markdown from `help_text` if it is configured in settings.
- If no help text is stored, the frontend falls back to bundled translations.
- Raw HTML is escaped before rendering.

## Deployment

- `docker-compose.yml` mounts a persistent `uploads_data` volume for backend uploads.
- `backend/uploads/` is ignored by git to prevent committing generated files.
