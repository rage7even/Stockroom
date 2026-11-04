# Stockroom — Inventory Management System

A local inventory application for a phone-accessories warehouse, built with Angular, Django and SQLite.

Workflow: receiving → order confirmation → reservation → packing → shipment, or cancellation with reservation release.

## Requirements

- Python 3.11+ available as `python` in PATH.
- Node.js 22.22.3+ in the 22.x series, or 24.15.0+ in the 24.x series, with npm.
- Windows for the supplied batch launchers; internet for initial installation.

## Start on Windows

1. Clone/download the entire project and open its root folder.
2. Double-click `setup.bat` once. It creates the virtual environment, installs dependencies, builds Angular and initializes the database.
3. Double-click `start.bat` and keep its terminal open.
4. Open http://127.0.0.1:8000.
5. Stop with Ctrl+C in the server terminal. Data survives restarts.

For later launches, only `start.bat` is needed. Do not open `index.html` directly.

| Demo role | Email | Password |
|---|---|---|
| Manager | manager@stockroom.local | Stockroom2026! |
| Sales | sales@stockroom.local | Stockroom2026! |
| Admin | admin@stockroom.local | Stockroom2026! |

These are fictional demonstration credentials. An empty database receives 18 products, three customers and three orders. Initialization preserves existing data. Registration creates a sales account.

## Manual setup

From the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe manage.py setup_stockroom
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe manage.py run_stockroom 127.0.0.1:8000 --noreload
```

An optional portable Node installation at `.tools/node-v22.22.3/node.exe` is used by `setup.bat` when present. It is excluded from Git; fresh clones need a supported Node installation.

## Development

Backend terminal, from the root:

```powershell
.\.venv\Scripts\python.exe manage.py run_stockroom 127.0.0.1:8000
```

Frontend terminal:

```powershell
cd frontend
npm.cmd start
```

Open http://127.0.0.1:4200. The proxy forwards `/api` to Django. Rebuild Angular after frontend changes when serving its compiled files through `start.bat`.

`run_stockroom` extends Django's development server with initialization and hourly backup/report checks. Standard `runserver` does not initialize demo data or start maintenance. The launch scripts are for local development and demonstration.

## Source map

| Path | Purpose |
|---|---|
| `manage.py` | Django command entry point |
| `backend/settings.py`, `urls.py`, `apps.py` | Configuration, URL routing and application registration |
| `backend/wsgi.py`, `asgi.py` | Server application entry points |
| `backend/models.py` | Managed ORM models and inventory annotations |
| `backend/forms.py` | JSON validation, strict integers and unknown-field rejection |
| `backend/api.py`, `middleware.py` | Sessions, roles, JSON errors and request guards |
| `backend/views.py` | API handlers and compiled Angular file serving |
| `backend/migrations/` | Versioned schema history and lossless adoption of the original tables |
| `backend/db.py`, `seed.py` | Database initialization, SQLite utilities and fictional seed data |
| `backend/backup.py`, `reports.py` | Consistent snapshots and stale-reservation CSV |
| `backend/management/commands/` | Setup, server and maintenance commands |
| `frontend/src/app/` | Angular pages, HTML templates, store and shared components |
| `frontend/src/styles.css` | Shared styling and responsive layout |
| `database/` | Reference SQL, business queries and fictional legacy database fixture |
| `integration/` | Request examples and offline restore utility |
| `qa/` | System/migration tests, input cases and HTTP smoke script |
| `docs/API.md`, `docs/ARCHITECTURE.md` | Shared technical documentation |

Personal defense guides and rehearsal notes stay local and are excluded from Git. Distribute them separately; a fresh clone does not include them.

## Business rules and permissions

`available = qty_in_stock - reserved`. Confirmed and packed orders reserve stock. Confirmation snapshots unit prices and records a reservation without reducing shelf stock. Cancellation releases the reservation; shipment reduces shelf stock and closes the reservation atomically. Repeated terminal actions are rejected.

Django `transaction.atomic()` and SQLite IMMEDIATE transactions take the write lock before availability is read. Failed multi-line orders and failed audit inserts roll back completely. Stock history has append-only SQL triggers.

| Capability | Sales | Manager | Admin |
|---|---|---|---|
| Read catalogue/customers/orders; create customers/orders | Yes | Yes | Yes |
| Edit products, receive/adjust stock, pack/ship/cancel, read history | No | Yes | Yes |
| Manage other accounts and backups | No | No | Yes |

Permissions are checked server-side. HttpOnly/SameSite Strict cookies contain random tokens; only their hashes are stored. Passwords use salted scrypt. Existing legacy hashes are upgraded after successful login. The application keeps its Staff/Session models; Django admin is not configured.

## API and checks

See [API reference](docs/API.md), [architecture](docs/ARCHITECTURE.md) and [request examples](integration/API_EXAMPLES.http). API paths have no trailing slash, accept JSON and use a session cookie. Errors contain `detail`.

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m unittest qa.test_system qa.test_migration -v
.\.venv\Scripts\python.exe -m qa.run_data_quality
.\.venv\Scripts\python.exe -m qa.http_smoke
```

There are 31 system tests, two migration tests and 20 data-quality cases. The working-database test skips if no local working database exists. Tests use temporary databases; migration tests modify copies. HTTP smoke needs a built frontend and starts its own server. Generated results are local and ignored. Browser end-to-end, physical equipment and production network performance require separate checks.

## Data, backups and migration

Working data: `data/stockroom.db`. Backups: `data/backups/`. Stale reservations older than 14 days: `data/stale-reservations.csv`.

While `run_stockroom` runs, maintenance checks immediately and hourly. Backups are due after 24 hours; the latest 30 are retained. CSV refreshes on the first check of each UTC day. `manage.py maintenance` performs one maintenance check.

Before upgrading an existing database, stop the server and create a snapshot:

```powershell
.\.venv\Scripts\python.exe -m backend.backup
```

The initial migration adopts existing tables without clearing rows. Future model changes need reviewed migrations, including preservation of dependent SQL views/triggers when SQLite rebuilds tables.

To restore, stop all database users. If WAL/SHM files remain, checkpoint after closing connections:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('data/stockroom.db'); print(c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchall()); c.close()"
```

Replace the sample filename with a real backup:

```powershell
.\.venv\Scripts\python.exe integration/restore_backup.py data/backups/stockroom-YYYYMMDD-HHMMSS-XXXXXX.db --server-stopped
```

Restore validates integrity/FKs, saves a safety copy and revokes sessions. Do not delete live sidecar files manually. Local snapshots do not protect against loss of the whole computer.

## Environment variables

| Variable | Purpose |
|---|---|
| `STOCKROOM_DB` | SQLite path; default `data/stockroom.db` |
| `STOCKROOM_DEMO` | `0` disables automatic fictional seed data |
| `DJANGO_SECRET_KEY` | Explicit secret for a configured deployment |
| `DJANGO_DEBUG` | Default `1` for local use; `0` disables debug |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `STOCKROOM_ALLOWED_ORIGINS` | Comma-separated trusted write origins |
| `STOCKROOM_SECURE_COOKIE` | `1` for a separately configured HTTPS deployment |

Do not commit real credentials or working databases. `database/demo_stockroom.db` is an intentional fictional legacy fixture.

## Scope and provenance

A student application for one local warehouse. Public shopping, payments, email delivery and MFA are outside its current scope. SQLite serializes writers. Production hosting needs a deployment server and operational configuration.

The baseline code and tests were AI-assisted. Team members should describe their actual reviewed contributions and verification accurately.
