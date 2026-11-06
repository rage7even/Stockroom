# Проверки 6 ноября 2026

- Django check: PASS.
- Angular production build: PASS (frontend_build.txt).
- 15 tests: PASS (tests.txt).
- 20 quantity input records: PASS (data_results.csv).
- Real HTTP: 20 clients, 100 inventory reads; p95 0.1763 seconds, target 1.5 seconds.
- Two simultaneous orders for four out of five units: HTTP 201 and HTTP 409.
- SQLite backup: integrity ok, no FK errors; restored into isolated memory database (backup_result.json).
- Full browser E2E, Windows batch execution, scanner and printer: NOT RUN.

Результаты получены ИИ в Linux. Dias должен повторить свои проверки и заполнить manual_checks.csv. Количество автотестов уменьшено по сравнению с большой версией, но сохранены основные бизнес-сценарии и отрицательные случаи. Реальный год retention и ночное расписание в течение суток не ожидались.
