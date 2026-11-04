import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from backend.db import connect, db_path


def backup_directory():
    return db_path().parent / 'backups'


def create_backup():
    folder=backup_directory()
    folder.mkdir(parents=True,exist_ok=True)
    name=datetime.now(timezone.utc).strftime('stockroom-%Y%m%d-%H%M%S-%f.db')
    target=folder / name
    source=connect()
    destination=sqlite3.connect(target)
    try:
        source.backup(destination)
        if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup integrity check failed')
    finally:
        source.close()
        destination.close()
    for old in sorted(folder.glob('stockroom-*.db'),reverse=True)[30:]:
        old.unlink()
    return target


def backup_if_due():
    files=list(backup_directory().glob('stockroom-*.db'))
    if not files or datetime.now(timezone.utc).timestamp()-max(p.stat().st_mtime for p in files)>86400:
        return create_backup()


if __name__ == '__main__':
    print(create_backup())
