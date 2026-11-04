import csv
from datetime import datetime,timezone
from backend.db import connect,db_path


def write_stale_report_if_due():
    target=db_path().parent/'stale-reservations.csv'
    today=datetime.now(timezone.utc).date()
    if target.exists() and datetime.fromtimestamp(target.stat().st_mtime,timezone.utc).date()==today:
        return
    with connect() as db:
        rows=db.execute("SELECT o.order_id,c.shop_name,o.confirmed_at,o.status,SUM(i.qty_reserved) AS reserved_units FROM orders o JOIN customer c ON c.customer_id=o.customer_id JOIN order_item i ON i.order_id=o.order_id WHERE o.status IN ('confirmed','packed') AND julianday(o.confirmed_at)<julianday('now','-14 days') GROUP BY o.order_id,c.shop_name,o.confirmed_at,o.status ORDER BY o.confirmed_at").fetchall()
    with target.open('w',newline='',encoding='utf-8-sig') as file:
        writer=csv.writer(file)
        writer.writerow(['Order ID','Shop','Confirmed UTC','Status','Reserved units'])
        writer.writerows(rows)
