# Кто какую часть объясняет

| Участник | Ответственность | Файлы | Проверяемый результат |
|---|---|---|---|
| Nurdaulet 24B031742 | Frontend | frontend/src/app, styles.css | Регистрация, Overview, поиск и карточка товара, форма и ошибка заказа |
| Aksungkar 24B031908 | Backend | inventory/views.py, services.py, serializers.py | Остаток проверяется сервером; резерв, отмена, отгрузка и history атомарны |
| Akylbek 24B032013 | База | inventory/models.py, migrations, database/queries.sql | Связанные таблицы, ключи, ограничения, реальные 18 товаров и SQL |
| Dias 24B032021 | QA | inventory/tests.py, qa | 15 тестов, 20 записей, ручной checklist и фактические результаты |
| Oren 24B031750 | Интеграция и релиз | config/urls.py, store.ts, proxy.conf.json, setup/start.bat | Полный путь frontend → API → DB и повторяемый запуск из чистого клона |

## Nurdaulet: порядок чтения

1. app.html: общий layout и router-outlet.
2. routes.ts: какая страница открывается по адресу.
3. products.ts и products.html: массив товаров из Store, фильтр, выбор товара.
4. store.ts: один метод request делает HTTP, refresh получает актуальные данные.
5. auth: ngModel, форма, вызов /auth/register или /auth/login.
6. orders: форма передаёт customer_id, channel и lines. Backend возвращает успех либо ошибку, Store обновляет состояние.

signal — данные, computed — значение, зависящее от данных. На защите покажи одну понятную цепочку, а не весь CSS. Оформление можно объяснить через sidebar, panel, table и media queries.

## Aksungkar: порядок чтения

urls.py → views.orders → OrderInput → services.confirm. В services.confirm сначала проверяются все товары, затем создаются заказ, строки и история. @transaction.atomic возвращает всё назад при ошибке. SQLite transaction_mode IMMEDIATE получает write lock до проверки остатков, поэтому конкурирующий запрос читает уже новый reserve. В этой версии select_for_update не используется как фиктивная защита SQLite.

Для отмены статус меняется на cancelled и пишется release. Для отгрузки уменьшается physical stock и пишется sale. Формула reserve считает только confirmed/packed.

## Akylbek: таблицы

- Staff — обычный расширенный Django User, используется также для login.
- Customer — магазин; Order ссылается на него по FK.
- Product — один SKU, цена и физический запас.
- Order — клиент, канал, статус и сотрудник.
- OrderItem — bridge для M:N между Order и Product. UNIQUE(order,product).
- StockMovement — событие изменения physical/reserved, сотрудник и время.

У Django есть дополнительные технические таблицы permissions, session и migrations; они не являются дополнительными бизнес-модулями. Цена unit_price_kzt в строке заказа фиксирует цену сделки. SQL-запрос ниже нельзя заменить пересчётом старых заказов по новой цене.

```mermaid
erDiagram
 Staff ||--o{ Order : creates
 Customer ||--o{ Order : places
 Order ||--|{ OrderItem : contains
 Product ||--o{ OrderItem : reserves
 Staff ||--o{ StockMovement : performs
 Product ||--o{ StockMovement : tracks
 Order o|--o{ StockMovement : explains
```

## Dias: проверки

Открой test_01: GIVEN 10 on shelf и 6 reserved, WHEN request 5, THEN 409 и available остаётся 4. test_07 намеренно ломает history и проверяет rollback. test_15 содержит 20 входных записей. qa/http_check.py проверяет два одновременных канала отдельными HTTP-запросами. Объясняй фактически выполненные свои проверки отдельно от приложенных результатов ИИ.

## Oren: интеграция и релиз

Обычный запуск — Django отдаёт собранный Angular и API на одном origin. При разработке Angular 4200 использует proxy к Django 8000. Cookie session и csrf передаются браузером/Store, пароль в localStorage не сохраняется.

Клонируйте [репозиторий команды](https://github.com/rage7even/Stockroom) и соберите Angular по [README](../README.md). Каждый участник делает собственную ветку, вносит изменение, проверяет его и открывает pull request. Интегратор проверяет, что после объединения изменений проект можно запустить из чистого клона и пройти сценарий заказа. Рабочая БД, venv, backups и node_modules исключены .gitignore. Приложенная database/demo.db содержит только вымышленные данные.
