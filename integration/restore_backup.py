import argparse
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description='Restore only while Stockroom is stopped. Existing data is preserved in a safety copy.')
    parser.add_argument('backup',type=Path)
    parser.add_argument('--target',type=Path,default=Path(__file__).resolve().parent.parent/'data'/'stockroom.db')
    parser.add_argument('--server-stopped',action='store_true',required=True)
    args=parser.parse_args()
    if not args.backup.is_file():
        parser.error('Backup file not found')
    if args.backup.resolve()==args.target.resolve():
        parser.error('Backup and target must be different files')
    source=sqlite3.connect(f'file:{args.backup.resolve().as_posix()}?mode=ro',uri=True)
    try:
        if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            parser.error('Backup integrity check failed')
        if source.execute('PRAGMA foreign_key_check').fetchall():
            parser.error('Backup has invalid foreign keys')
        tables={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'staff','customer','product','orders','order_item','stock_movement','session'}.issubset(tables):
            parser.error('Not a Stockroom backup')
        if any(args.target.parent.glob(args.target.name+'-*')):
            parser.error('SQLite sidecar files exist. Stop the server and checkpoint the database before restoring. See README.md.')
        args.target.parent.mkdir(parents=True,exist_ok=True)
        if args.target.exists():
            safety=args.target.with_name('before-restore-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.db')
            shutil.copy2(args.target,safety)
            print('Safety copy:',safety)
        with sqlite3.connect(args.target) as destination:
            source.backup(destination)
            destination.execute('DELETE FROM session')
        print('Restored. All users must sign in again.')
    finally:
        source.close()


if __name__=='__main__':
    main()
