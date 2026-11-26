# Акылбек · схема БД двух видов переписки · 24B032013

## Что показать

1. После переписки Manager ↔ Admin откройте модели и найдите одну запись `DirectConversation` с двумя ссылками на `Staff`. Покажите два сообщения с разными отправителями в `DirectMessage`.
2. В коде найдите ограничения `direct_members_sorted` и `direct_members_unique`. Они требуют два разных ID в каноническом порядке и не дают создать второй диалог для той же пары.
3. Сравните с чатом закупки. `PurchaseConversation` однозначно связан с `PurchaseOrder`. Через `PurchaseOrder.supplier` и `Staff.supplier` сервер находит доступ поставщика.
4. Покажите индекс `direct_message_thread_idx`, который поддерживает чтение сообщений диалога по ID, и уникальность `request_id` в таблице сообщений.

## Что открыть в коде

| Источник | Что показать |
| --- | --- |
| [models.py](../../backend/inventory/models.py) · `DirectConversation`, `DirectMessage`, `PurchaseConversation`, `PurchaseMessage` | Ключи, связи, UUID и индексы. |
| [0008_week13.py](../../backend/inventory/migrations/0008_week13.py), [0009_staff_chat.py](../../backend/inventory/migrations/0009_staff_chat.py) | Сначала появляются таблицы закупочных чатов, затем добавляются таблицы личных чатов. |
| [test_staff_chat.py](../../backend/inventory/test_staff_chat.py) · `test_members_exchange_messages_and_share_one_conversation` | Проверяет одну строку диалога для обоих направлений и отказ при попытке создать дубль. |

### Запрос для показа в SQLite

Выполните на учебной БД после отправки сообщений.

```sql
SELECT c.id AS dialog_id, c.first_id, c.second_id,
       m.id AS message_id, m.sender_id, m.created_at
FROM inventory_directconversation AS c
JOIN inventory_directmessage AS m ON m.conversation_id = c.id
ORDER BY c.id, m.id;
```

## Что сказать

«Один личный диалог хранит пару сотрудников. Каждое сообщение отдельно хранит автора и дату. Для закупок хозяин диалога определяется номером закупки. Сумма, остаток товара и история заказов в этих таблицах не меняются».

**Передача слова.** «Диас проверит фильтры, ошибки и то, что отклонённый текст отсутствует в истории».
