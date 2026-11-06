# Требования и статус

| Основание | Что есть в этой версии | Статус / доказательство |
|---|---|---|
| Task 4 FR-1 | Отказ при request > available | test_01 и HTTP race |
| Task 4 FR-2 | Reserve при подтверждении, не при отгрузке | test_02, test_03 |
| Task 4 FR-3 | Каждая складская операция имеет staff, SKU, delta, time | test_10, append-only history |
| Business rule | available = physical − active reservations, не меньше 0 через API | test_06, test_11 |
| NFR-1 | 95% проверок ≤1.5 s при 20 пользователях | Локальные 20 HTTP-клиентов ×5 запросов; qa/http_results.json. Не промышленная гарантия. |
| NFR-2 latency | History пишется в той же транзакции | Синхронная проверка audit; отдельные 3 секунды не измерялись |
| NFR-2 retention | Нет очистки history; update/delete запрещены | Триггеры и test_12; реальный год не прошёл |
| Task 5 | Ручной SKU как fallback, scanner как keyboard input | Форма Receiving. Физические устройства, USB policy, QR/printer и внешний SSD не испытаны/не реализованы приложением |
| Task 6 | Проверенные backups, 30 копий, восстановление | Команда maintenance и integration/restore.py. Копии пока на том же устройстве; нужен внешний носитель. |
| Task 7 | Unique lines, FK, integer quantities, даты сервера | test_12, test_15. Accuracy fictional data = NOT VERIFIABLE. |
| Task 7 stale | Manager видит >14 days в Orders и CSV | test_13. CSV обновляется hourly при работающем сервере; email не подключён |
| Task 9 | 6 бизнес-таблиц, PK/FK, M:N bridge, ERD, SQL | models.py, TEAM.md, queries.sql и demo.db |
| Task 9 cancel | Отмена освобождает запас и оставляет trace | test_04 |
| Week 10 frontend | Регистрация, главная, детали товаров | Все три экрана реализованы; browser checklist ещё выполнить своей командой |
| Week 10 backend | API и бизнес-логика | views/services/serializers, unit + HTTP checks |
| Week 10 DB | Созданные таблицы и SQL | Реальная demo.db, 18 товаров |
| Week 10 QA | 15–20 records и QA report | 20 входных записей, qa/data_results.csv и TEST_REPORT.md |
| Week 10 integration | Angular соединён с Django и SQLite | HTTP check и инструкция запуска из репозитория команды. |
| Weekly / Week 15 | Основной процесс работает; отдельный вклад 5 человек | DEFENCE.md и CONTRIBUTION.md; личный вклад ещё требуется подтвердить |

Программные функции, результаты проверок, работа с оборудованием и будущие задачи обозначены отдельно. Ручные проверки и организационные части hardware-плана требуют отдельных подтверждений.

Физический firewall/USB policy — операционные меры, приложение их не устанавливает. Доступ к самому файлу SQLite должен быть ограничен владельцем ноутбука; роли приложения проверяются сервером, а не SQL GRANT.
