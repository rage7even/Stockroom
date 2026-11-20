# Нурдаулет · интерфейс закупок

**Твоя зона защиты** — три экрана закупок, переходы между ними, формы и состояние Angular. Если остаётся время, покажи тёмную тему.

## Показ на сайте

1. В **Suppliers** выбери **Demo Manufacturer Week 12**. Покажи Almaty, срок **5 days**, активный договор, закупочную цену и дату обновления **Supplier stock**. Объясни, что число в этом столбце — последнее сообщённое наличие у поставщика. Покажи форму **Edit supplier** или **Add offer**, затем закрой её.
2. В **Purchase orders** нажми **View order** для учебной поставки. Покажи ожидаемую дату, позицию и поля **Ordered / Received / Remaining**. Нажми **Mark in transit**, затем **Receive delivery**.
3. В **Purchase receiving** покажи, что нужный заказ выбран автоматически. Назови столбцы **Already received**, **Receive now**, **Still expected**. История появится под таблицей после первой приёмки. Передай управление Орену для демонстрации сканирования.
4. Если попросят показать создание заказа, вернись в **Suppliers → Create purchase order**. Укажи количество у нужного товара и нажми **Place purchase order** только для отдельного учебного заказа. Для основного показа используйте один согласованный номер.

## Исходники

| Файл и функции | Что защищать |
| --- | --- |
| [routes.ts](../../frontend/src/app/routes.ts#L27), [app.ts](../../frontend/src/app/app.ts) | Маршруты `/suppliers`, `/purchases` и `/purchase-receiving`. Пункты закупок помечены как доступные складским ролям. |
| [suppliers.ts · load, saveSupplier, saveOffer](../../frontend/src/app/suppliers.ts#L30), [suppliers.html](../../frontend/src/app/suppliers.html) | Загружаем поставщиков и их ассортимент. Для сохранения формы вызываем POST или PUT. После ответа заменяем строку поставщика в состоянии. |
| [purchases.ts · validOrder / load / create / ship](../../frontend/src/app/purchases.ts#L31), [purchases.html](../../frontend/src/app/purchases.html) | `computed` собирает и проверяет строки заказа. `create()` отправляет `supplier_id` и позиции. `ship()` меняет в интерфейсе статус после успешного ответа. |
| [purchase-receiving.ts · valid / load / choose / confirm](../../frontend/src/app/purchase-receiving.ts#L29), [purchase-receiving.html](../../frontend/src/app/purchase-receiving.html) | Параметр `?order=` выбирает заказ. Валидатор сравнивает введённые количества с ожидаемыми. `confirm()` отправляет строки и идентификатор приёмки, обновляет экран и общие данные склада. Орен отдельно показывает `scan()`. |
| [purchase-types.ts](../../frontend/src/app/purchase-types.ts), [store.ts · request](../../frontend/src/app/store.ts#L30) | Типы описывают данные UI. `request()` передаёт вызовы под `/api` с сессией и применяет CSRF для записывающих запросов. Ошибки сервера выводятся в форме. |
| [theme-toggle.ts · toggle](../../frontend/src/app/theme-toggle.ts#L26), [dark-theme.css](../../frontend/src/dark-theme.css), [index.html](../../frontend/src/index.html#L9) | Луна и солнце переключают `data-theme` на HTML. Выбор хранится в `localStorage` и считывается при загрузке страницы. |

**Что сказать.** «Поставщик, заказ и приёмка связаны идентификаторами в маршрутах. Пользователь видит следующий шаг и оставшееся количество по строке. Angular помогает проверить форму, а Django повторяет проверку перед записью».

**Передача слова.** «Страница приёмки уже открыта с нужным заказом. Акылбек покажет, как заказ связан с приёмками в базе, а потом Орен продемонстрирует поиск товара по штрихкоду».
