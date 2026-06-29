# План: Pipeline Parser → InviteCampaign → InviteTask

## Текущая ситуация
- Две модели `ParsedChat`: `parser/models.py` (основная) и `parsed_chats/models.py` (дубль)
- Две модели кампаний: `Campaign` (старая, campaigns/models.py) и `InviteCampaign` (новая, inviter/models.py)
- `_get_target_users()` возвращает хардкод
- `InviteCampaign` уже имеет API роуты в `inviter/api.py`
- `ParsedUser` существует в `parser/models.py` с таблицей `parsed_users`

## Шаги
1. **Удалить дубль ParsedChat** (`parsed_chats/models.py`) — заменить импорты на `parser.models.ParsedChat`
2. **Изолировать старую Campaign**: заменить TYPE_CHECKING ссылки на InviteCampaign в parser/models.py
3. **Обновить db/models.py** — правильные импорты
4. **Добавить в InviteCampaign поле `source_parsed_chat_id`** для прямой связи с ParsedChat
5. **Переделать `_get_target_users()`** — читать из ParsedUser через source_parsed_chat_id
6. **Запуск кампании**: создавать InviteTask из реальных parsed_users
7. **Защита от дублей**: проверять существующие InviteTask
8. **Blacklist/skip**: уже есть, используем
9. **Тесты**: минимальные тесты на создание задач из ParsedChat