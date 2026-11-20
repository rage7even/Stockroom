# Stockroom

Stockroom is our course project for a small warehouse that sells phone accessories. We use Angular for the interface, Django for the API, and SQLite for the database. The app lets staff track products, reserve stock for customer orders, receive deliveries, and see who changed the stock.

- [User guide](docs/USER_GUIDE.md) for staff who work with products, orders, and deliveries.
- [Developer guide](docs/DEVELOPER_GUIDE.md) for contributors who run, change, test, or recover the app.
- [Windows and WSL quick start](docs/RUN_LOCAL.md) for the shared Python launcher and VS Code setup (in Russian).

## Run it on Windows

If you downloaded the project ZIP with the compiled frontend, extract it, run `setup.bat` once, and then run `start.bat`. For a source checkout, build Angular first using the steps below.

You need Git, Python 3.11 or newer, and Node.js 22.22.3 or later in the 22.x line (or 24.15.0 or later in the 24.x line). The setup also works with Python 3.11 from MSYS2 if `python` is on your PATH.

Open PowerShell and run these commands one at a time. Run `setup.bat` only after the Angular build succeeds.

```powershell
git clone https://github.com/rage7even/Stockroom.git
Set-Location Stockroom/frontend
npm.cmd ci
npm.cmd run build
Set-Location ..
.\setup.bat
.\start.bat
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). `setup.bat` creates a virtual environment, applies the database migrations, and fills an empty database with sample data. After that, run `start.bat` from the project folder whenever you need the app. Press **Ctrl+C** to stop it. Rebuild Angular after changing its source files.

| Role | Demo login |
| --- | --- |
| Manager | `manager@stockroom.local` |
| Sales | `sales@stockroom.local` |
| Admin | `admin@stockroom.local` |

The password for all three demo accounts is `Stockroom2026!`.

### Add staff accounts

The administrator creates accounts in [Django admin](http://127.0.0.1:8000/admin/). For a local demo, sign in with the Admin account from the table above.

In Django admin, select **Staffs → Add**. Enter the employee's email in **Username** so they can use it to sign in to Stockroom, and choose the **Sales** or **Manager** role. Keep Django's staff and superuser flags for accounts that need to administer Django.

## Try an order

1. Sign in as Manager and find `BAS-C65W-WHT` in **Products**. On a fresh database it has 10 units on the shelf, 6 reserved, and 4 available.
2. In **Orders**, try to confirm an order for 5 units. The API rejects it because only 4 are available.
3. Confirm an order for 4 units. The shelf count stays at 10 and the available count drops to 0.
4. Cancel the new order. The reserve is released and the available count goes back to 4. Check **History** for the reserve and release entries.

Angular sends requests under `/api`. Django checks the session and stock, updates SQLite, and returns JSON that Angular uses to refresh the page. For frontend development, run Django on port 8000 and `npm.cmd start` from `frontend` in another terminal. The Angular dev server on port 4200 forwards `/api` to Django.

## Tests

From the project folder, with `setup.bat` already run:

```powershell
$stockroomPython = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $stockroomPython)) { $stockroomPython = '.\.venv\bin\python.exe' }
& $stockroomPython backend\manage.py test inventory --noinput
```

The [QA report](qa/TEST_REPORT.md) describes the automated checks. The [manual checklist](qa/manual_checks.csv) covers the browser flows.

## Week 12 purchasing demo

Sign in as Manager and open **Suppliers**, **Purchase orders** and **Purchase receiving**. The [user guide](docs/USER_GUIDE.md#buy-from-a-supplier) covers the complete flow. To add a sample supplier and a 10-unit purchase on a demo database, run `backend/manage.py seed_week12` using the same Python interpreter as the test command, after `seed` and `seed_week11`.

## Database backups

The live database is `backend/stockroom.db`. When the server starts and once an hour while it runs, it checks whether a daily backup is due. It keeps up to 30 snapshots in `backend/backups`. Keep a copy on a separate drive if you need to recover after losing the computer. The live database and backups stay out of Git. The checked-in `database/demo.db` contains fictional data used by the HTTP checks.

To restore a snapshot, stop the server and close anything else using the database. From the project folder, use the `$stockroomPython` variable from the tests section and substitute the real backup filename:

```powershell
& $stockroomPython integration\restore.py 'backend\backups\stockroom-EXAMPLE.db' --server-stopped
```

The restore script validates the snapshot and saves a copy of the current database before replacing it. Run `backend/manage.py migrate` with the same Python interpreter before restarting, then sign in again.
