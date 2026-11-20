import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

p = argparse.ArgumentParser(
    description="Restore a Stockroom Study backup. Stop the server first."
)
p.add_argument("backup", type=Path)
p.add_argument("--server-stopped", action="store_true", required=True)
a = p.parse_args()
target = Path(__file__).resolve().parents[1] / "backend/stockroom.db"
if not a.backup.is_file() or a.backup.resolve() == target.resolve():
    p.error("Choose a different, existing backup file.")
if any(target.parent.glob("stockroom.db-*")):
    p.error("SQLite sidecar files exist. Close all database connections first.")
with sqlite3.connect(
    f"file:{a.backup.resolve().as_posix()}?mode=ro", uri=True
) as source:
    if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        p.error("Backup is damaged.")
    if source.execute("PRAGMA foreign_key_check").fetchall():
        p.error("Backup has invalid references.")
    names = {
        r[0]
        for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if not {
        "staff",
        "product",
        "orders",
        "order_item",
        "stock_movement",
        "django_session",
    }.issubset(names):
        p.error("Not a Stockroom Study database.")
    if target.exists():
        shutil.copy2(
            target,
            target.with_name(
                "before-restore-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".db"
            ),
        )
    with sqlite3.connect(target) as destination:
        source.backup(destination)
        destination.execute("DELETE FROM django_session")
print("Restored. Sign in again. A safety copy of the previous database was kept.")
