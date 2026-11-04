import os
from pathlib import Path
from backend.db import initialize,connect

if __name__=='__main__':
    target=Path(__file__).resolve().parent/'demo_stockroom.db'
    os.environ['STOCKROOM_DB']=str(target)
    os.environ['STOCKROOM_DEMO']='1'
    initialize()
    with connect() as db:
        print('Demo database:',target)
        for table in ('product','customer','orders','order_item','stock_movement','staff'):
            print(table,db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0])
