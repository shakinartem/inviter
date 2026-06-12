# Plan: Settings, Branding, Language Switcher, Help Section

## 1. Backend
- **Модель `SiteSettings`** в `backend/app/features/settings/` — singleton-таблица (одна запись) с полями:
  - id, language (ru/en), site_name, logo_path, help_text, system_config (JSON), created_at, updated_at
- **Миграция Alembic** — создание таблицы `site_settings`
- **API endpoints** под `/api/v1/settings`:
  - `GET /settings` — получить настройки
  - `PUT /settings` — обновить настройки
  - `POST /settings/logo` — загрузить логотип (multipart)
- **Сохранение логотипа** — в `backend/uploads/logo/` (добавить в .gitignore)

## 2. Frontend
- **Новая страница `/settings`**:
  - Язык (RU/EN) — переключатель
  - Название сайта — текстовое поле
  - Загрузка логотипа — file input + preview
  - Системные настройки (JSON-редактор или key-value)
  - Кнопка сохранения
- **Новая страница `/help`**:
  - Текст инструкции (редактируемый, если есть права)
- **Language switcher** — компонент в layout (sidebar/header)
- **Логотип** — отображение в sidebar/header
- **i18n** — простая реализация без библиотек: объект с ключами ru/en

## 3. Порядок работ
1. Создать модель и миграцию
2. Создать API endpoints
3. Создать сервисный слой
4. Обновить .gitignore
5. Обновить .env.example при необходимости
6. Создать frontend-страницы
7. Создать i18n-словарь
8. Обновить роутер и layout
9. Проверить сборку
10. Подготовить git-коммит
</plan.md>
</write_to_file>