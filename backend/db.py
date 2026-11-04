import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent.parent


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def db_path():
    from django.conf import settings
    if settings.configured:
        from django.db import connection
        return Path(connection.settings_dict['NAME'])
    return Path(os.environ.get('STOCKROOM_DB', str(ROOT / 'data' / 'stockroom.db')))


class ManagedConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect():
    db_path().parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path(), timeout=15, factory=ManagedConnection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


# Direct SQL helper for QA and offline utilities. HTTP business logic uses Django atomic().
@contextmanager
def transaction():
    db = connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(verbosity=0):
    import django
    from django.apps import apps
    from django.core.management import call_command
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    if not apps.ready:
        django.setup()
    db_path().parent.mkdir(parents=True, exist_ok=True)
    call_command('migrate', interactive=False, verbosity=verbosity)
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
    if os.environ.get('STOCKROOM_DEMO', '1') == '1':
        from backend.seed import seed_demo
        seed_demo()
