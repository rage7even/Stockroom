# Stockroom developer guide

Stockroom is a local warehouse app. Angular renders the screens, Django REST Framework serves the API, and SQLite stores staff, customers, products, orders, and stock movements.

## Get a development copy running

Follow the [Windows setup](../README.md#run-it-on-windows) once to install dependencies, build Angular, and create the demo database. For live frontend changes, stop `start.bat` first and open two PowerShell terminals in the repo root.

In the first terminal, start Django on port 8000:

```powershell
$stockroomPython = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $stockroomPython)) { $stockroomPython = '.\.venv\bin\python.exe' }
& $stockroomPython backend\manage.py runserver 127.0.0.1:8000
```

In the second terminal, start Angular:

```powershell
Set-Location frontend
npm.cmd start
```

Open [http://127.0.0.1:4200](http://127.0.0.1:4200). The Angular dev proxy sends `/api` to Django on port 8000. Use `127.0.0.1` consistently so browser cookies work as expected. For the single-server setup, rebuild Angular with `npm.cmd run build` from `frontend` and use `start.bat` from the repo root. Django serves that build and the API on port 8000.

## Find the code

| Area | Where to start |
| --- | --- |
| Pages, navigation, and HTTP requests | [Angular routes](../frontend/src/app/routes.ts), [Store](../frontend/src/app/store.ts), and each page's `.ts` and `.html` files |
| API paths and role checks | [URL config](../backend/config/urls.py) and [views](../backend/inventory/views.py) |
| Request validation and stock rules | [Serializers](../backend/inventory/serializers.py) and [services](../backend/inventory/services.py) |
| Tables, seed data, and sample SQL | [Models](../backend/inventory/models.py), [migrations](../backend/inventory/migrations), [seed command](../backend/inventory/management/commands/seed.py), and [queries](../database/queries.sql) |
| Scheduled maintenance and recovery | [Server command](../backend/inventory/management/commands/run_stockroom.py), [maintenance](../backend/inventory/management/commands/maintenance.py), and [restore script](../integration/restore.py) |

## Follow an order through the API

1. The Orders page calls the Angular Store with a customer ID, a sales channel, and lines containing a SKU and quantity. The Store sends `POST /api/orders`.
2. Django checks the authenticated session, validates the request, and calls `services.confirm`. The browser sends the session cookie and the CSRF token in `X-CSRFToken` for writes. The Store obtains the token from `GET /api/auth/csrf` when needed.
3. The service calculates availability as physical stock minus the quantities reserved by confirmed and packed orders. It checks all lines and writes the order, its lines, and the stock movement entries in one transaction. An order that exceeds stock receives `409`. A successful order receives `201` with an `order_id`.
4. Angular reloads the product and order data. `GET /api/products` returns physical, reserved, and available quantities. Packing keeps the reservation in place, cancellation releases it, and shipment reduces physical stock and closes the reservation.

| Request | Purpose |
| --- | --- |
| `POST /api/auth/login`, `GET /api/auth/me` | Sign in and load the current staff member. |
| `GET /api/products`, `GET /api/orders`, `GET /api/customers` | Load warehouse data. |
| `POST /api/orders` | Confirm an order and reserve stock. |
| `POST /api/orders/<order_id>/pack`, `/ship`, or `/cancel` | Update an order as Manager or Admin. |
| `POST /api/stock/receive` or `/adjust`, `GET /api/movements` | Record physical stock changes or read stock history as Manager or Admin. |

## Check a change

From the repo root, run the Django tests with the same `$stockroomPython` variable:

```powershell
& $stockroomPython backend\manage.py test inventory --noinput
```

For frontend changes, build Angular and run the relevant steps in the [browser checklist](../qa/manual_checks.csv). For an order change, confirm that requesting 5 units of `BAS-C65W-WHT` on a fresh demo database is rejected, then reserve 4 and cancel. The available count should go from 4 to 0 and back to 4. Use the browser's **Network** panel to check the API responses if the screen and stock count disagree.

## Back up and restore SQLite

The default working database is `backend/stockroom.db`. Keep it and its backups out of Git. The `database/demo.db` fixture contains fictional data and is used by the HTTP checks.

### What the app does

1. `start.bat` runs the `run_stockroom` command. It calls `maintenance` when the server starts and once an hour while it is running.
2. If there is no snapshot, or the newest one is over 24 hours old, SQLite's backup API writes a dated snapshot under `backend/backups`. The command runs `PRAGMA integrity_check` and, after a successful check, keeps the newest 30 snapshots.
3. Copy a verified snapshot to a separate drive if you need to recover after losing the computer. A restored database reflects the time of that snapshot. Orders and changes made after that time need to be reconciled separately.

The regular development `runserver` command leaves the maintenance schedule disabled. From the repo root you can request a check manually:

```powershell
& $stockroomPython backend\manage.py maintenance
```

This uses the same 24-hour rule. Check the timestamp of the newest file before treating it as a fresh copy.

### Run a recovery drill

1. Use a disposable project copy with its own demo database and an empty backup folder. Start it with the development `runserver` command. Create a test order and record its order ID, product availability, and stock-history entry.
2. Stop the server and run `maintenance`. Check that a new snapshot was created, then copy it to a separate location. Rename `backend/stockroom.db` in the disposable copy to simulate a missing database.
3. Keep the server and database tools closed. Use the actual path to the saved snapshot and run the following command from the disposable project folder:

```powershell
& $stockroomPython integration\restore.py 'E:\StockroomBackup\stockroom-EXAMPLE.db' --server-stopped
```

4. Restart the app, sign in, and verify that the order, availability, and history match what you recorded. Note the snapshot time and how long recovery took.

The restore script checks database integrity, foreign keys, and expected tables. It writes to the default `backend/stockroom.db` beside this checkout, even if `STOCKROOM_DB` was used for a custom server path. It keeps a safety copy if the destination already exists and clears restored login sessions, so users sign in again.
