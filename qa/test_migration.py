"""Adopt real pre-Django snapshots twice and compare every business row."""
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLES = ('staff', 'session', 'customer', 'product', 'orders', 'order_item', 'stock_movement')


def snapshot(path):
    with closing(sqlite3.connect(path)) as db:
        return {table: db.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall() for table in TABLES}


class MigrationTests(unittest.TestCase):
    def check_snapshot(self, source):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'migrated.db'
            with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as old:
                with closing(sqlite3.connect(target)) as new:
                    old.backup(new)
            before = snapshot(target)
            env = {**os.environ, 'STOCKROOM_DB': str(target), 'STOCKROOM_DEMO': '1'}
            for _ in range(2):
                result = subprocess.run([sys.executable, 'manage.py', 'setup_stockroom', '--verbosity', '0'],
                                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(snapshot(target), before)
            with closing(sqlite3.connect(target)) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
                self.assertEqual(db.execute("SELECT COUNT(*) FROM django_migrations WHERE app='backend' AND name='0001_initial'").fetchone()[0], 1)

    def test_bundled_legacy_database_is_preserved(self):
        self.check_snapshot(ROOT / 'database' / 'demo_stockroom.db')

    def test_working_database_copy_is_preserved(self):
        path = ROOT / 'data' / 'stockroom.db'
        if not path.exists():
            self.skipTest('No local working database')
        self.check_snapshot(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
