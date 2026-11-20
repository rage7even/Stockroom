# Акылбек · каталог, CSV, индексы

## Что показать

1. Войди как **Manager**. Открой **Products** и покажи число у **All products**. Введи `LAB-` в поиск и покажи учебные товары. Очисти поиск, примени **Low stock** или выбери категорию.
2. Нажми **Import CSV** и выбери [файл для показа](../../database/week11-catalog.csv). Найди товары `CSV-C30W-WHT` и `CSV-CBL1-BLK`. Если файл уже импортировали на репетиции, заранее скопируй CSV и замени оба SKU на новые значения того же формата, например `CSV-C31W-WHT` и `CSV-CBL2-BLK`.
3. Нажми **Export CSV** и открой выгрузку. Покажи заголовки и добавленные строки. Импортируй тот же файл ещё раз и покажи ошибку дубликата.

## Что сказать

«Я показываю расширенный каталог. Сто учебных товаров имеют отдельные SKU и разные остатки, включая нулевой. Импорт проверяет весь файл перед записью, поэтому строка с ошибкой останавливает импорт. SKU — ключ товара. Индекс по статусу и дате помогает запросам, которые ищут заказы по этим полям».

## Какой код открыть

- [seed_week11.py](../../backend/inventory/management/commands/seed_week11.py) — `add_catalogue` создаёт 100 позиций, повторный запуск сохраняет существующие SKU.
- [week11.py](../../backend/inventory/week11.py) — `catalog_csv` проверяет заголовки, числа и дубликаты перед `bulk_create`.
- [models.py](../../backend/inventory/models.py) — `Product.sku`, связь `OrderItem` и индекс `orders_status_date_idx`.
- [Миграция 0003](../../backend/inventory/migrations/0003_week11.py) — операция `AddIndex`.

Проверка количества из WSL:

```bash
docker compose exec -T stockroom python backend/manage.py shell -c 'from inventory.models import Product; print("LAB:", Product.objects.filter(sku__startswith="LAB-D").count()); print("All:", Product.objects.count())'
```
