import sqlite3
import unittest
import hashlib
import secrets
from contextlib import closing
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from qa.django_support import JsonClient, isolated_database
from django.db import connections
from django.utils import timezone
from backend.api import attempts
from backend.models import Staff
from backend.security import token_hash
from backend.db import connect, transaction
from backend.backup import create_backup


class StockroomTests(unittest.TestCase):
    def setUp(self):
        self.context=isolated_database()
        self.folder=self.context.__enter__()
        attempts.clear()
        self.client=JsonClient()
        self.signin('manager')

    def tearDown(self):
        self.context.__exit__(None,None,None)

    def signin(self,role):
        return self.client.post('/api/auth/login',data={'login':role+'@stockroom.local','password':'Stockroom2026!'})

    def product(self,sku='BAS-C65W-WHT'):
        return next(p for p in self.client.get('/api/products').json() if p['sku']==sku)

    def order(self,qty,sku='BAS-C65W-WHT',**kwargs):
        return self.client.post('/api/orders',data={'customer_id':1,'channel':'sales_manager','lines':[{'sku':sku,'qty':qty}],**kwargs})

    def test_01_acceptance_reject_5_when_only_4_available(self):
        before=self.product()
        response=self.order(5)
        self.assertEqual(response.status_code,409)
        self.assertIn('Only 4 units',response.json()['detail'])
        self.assertEqual(self.product(),before)

    def test_02_exact_available_is_allowed(self):
        self.assertEqual(self.order(4).status_code,201)
        self.assertEqual(self.product()['available'],0)

    def test_03_confirm_reserves_without_changing_shelf(self):
        self.order(2)
        p=self.product()
        self.assertEqual((p['qty_in_stock'],p['reserved'],p['available']),(10,8,2))

    def test_04_cancellation_releases_reservation_once(self):
        oid=self.order(3).json()['order_id']
        self.assertEqual(self.client.post(f'/api/orders/{oid}/cancel').status_code,200)
        self.assertEqual(self.product()['available'],4)
        self.assertEqual(self.client.post(f'/api/orders/{oid}/cancel').status_code,409)
        self.assertEqual(self.product()['available'],4)

    def test_05_shipment_reduces_shelf_and_closes_reservation(self):
        oid=self.order(3).json()['order_id']
        self.assertEqual(self.client.post(f'/api/orders/{oid}/pack').status_code,200)
        self.assertEqual(self.product()['available'],1)
        self.assertEqual(self.client.post(f'/api/orders/{oid}/ship').status_code,200)
        p=self.product()
        self.assertEqual((p['qty_in_stock'],p['reserved'],p['available']),(7,6,1))
        self.assertEqual(self.client.post(f'/api/orders/{oid}/ship').status_code,409)

    def test_06_failed_multiline_order_rolls_back_every_line(self):
        before=self.product('ANK-C20W-WHT')
        response=self.client.post('/api/orders',data={'customer_id':1,'channel':'website','lines':[{'sku':'ANK-C20W-WHT','qty':2},{'sku':'BAS-C65W-WHT','qty':5}]})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.product('ANK-C20W-WHT'),before)
        with connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],3)

    def test_07_simultaneous_channels_cannot_oversell(self):
        cookie=self.client.cookies['stockroom_session'].value
        def submit(channel):
            client=JsonClient()
            client.cookies['stockroom_session']=cookie
            try:
                return client.post('/api/orders',data={'customer_id':1,'channel':channel,'lines':[{'sku':'ANK-C20W-WHT','qty':4}]}).status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(submit,['website','sales_manager']))
        self.assertEqual(sorted(results),[201,409])
        self.assertEqual(self.product('ANK-C20W-WHT')['available'],1)

    def test_08_duplicate_sku_lines_rejected(self):
        response=self.client.post('/api/orders',data={'customer_id':1,'channel':'website','lines':[{'sku':'ANK-C20W-WHT','qty':1},{'sku':'ANK-C20W-WHT','qty':1}]})
        self.assertEqual(response.status_code,422)

    def test_09_zero_negative_fractional_and_boolean_quantities_rejected(self):
        for qty in (0,-1,1.5,True):
            with self.subTest(qty=qty):
                self.assertEqual(self.order(qty).status_code,422)

    def test_10_unknown_customer_and_product_rejected(self):
        self.assertEqual(self.order(1,customer_id=999).status_code,422)
        self.assertEqual(self.order(1,sku='NON-EXIST-BLK').status_code,422)

    def test_11_receive_and_manual_audit(self):
        response=self.client.post('/api/stock/receive',data={'sku':'HOC-U72-BLK','quantity':5,'source':'manual','note':'Delivery note DN-01'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.product('HOC-U72-BLK')['available'],9)
        movement=self.client.get('/api/movements').json()[0]
        self.assertEqual((movement['physical_delta'],movement['source'],movement['staff_name']),(5,'manual','Aisulu Manager'))

    def test_12_correction_cannot_consume_reserved_stock(self):
        response=self.client.post('/api/stock/adjust',data={'sku':'BAS-C65W-WHT','quantity':-5,'source':'manual','note':'Shelf recount'})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.product()['qty_in_stock'],10)

    def test_13_sales_permissions_enforced_server_side(self):
        self.signin('sales')
        self.assertEqual(self.order(1).status_code,201)
        self.assertEqual(self.client.get('/api/movements').status_code,403)
        self.assertEqual(self.client.get('/api/staff').status_code,403)
        self.assertEqual(self.client.post('/api/backups',data={}).status_code,403)
        self.assertEqual(self.client.post('/api/stock/receive',data={'sku':'BAS-C65W-WHT','quantity':1,'source':'manual','note':'Test delivery'}).status_code,403)
        self.assertEqual(self.client.post('/api/orders/ORD-2026-0001/cancel').status_code,403)

    def test_14_login_cookie_logout_and_unauthenticated_access(self):
        self.client.post('/api/auth/logout')
        self.assertEqual(self.client.get('/api/products').status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',data={'login':'manager@stockroom.local','password':'incorrect'}).status_code,401)
        r=self.signin('manager')
        cookie=r.cookies['stockroom_session'].output().lower()
        self.assertIn('httponly',cookie)
        self.assertIn('samesite=strict',cookie)
        self.assertEqual(self.client.get('/api/products').status_code,200)

    def test_15_registration_defaults_to_sales_and_rejects_role_injection(self):
        payload={'full_name':'New Person','login':'new@example.test','password':'LongPassword123!'}
        self.assertEqual(self.client.post('/api/auth/register',data={**payload,'role':'admin'}).status_code,422)
        r=self.client.post('/api/auth/register',data=payload)
        self.assertEqual(r.status_code,201)
        self.assertEqual(r.json()['role'],'sales')
        self.assertEqual(self.client.get('/api/auth/me').json()['full_name'],'New Person')
        self.assertEqual(self.client.post('/api/auth/register',data=payload).status_code,409)

    def test_16_product_validation_and_normalized_customer(self):
        data={'sku':'TST-C20W-BLK','product_name':'Test Charger','brand':'Test','category':'Chargers','price_kzt':1234,'reorder_level':5,'location':'X-01'}
        self.assertEqual(self.client.post('/api/products',data=data).status_code,201)
        self.assertEqual(self.client.post('/api/products',data=data).status_code,409)
        self.assertEqual(self.client.post('/api/products',data={**data,'sku':'lower-case-blk'}).status_code,422)
        self.assertEqual(self.client.post('/api/products',data={**data,'sku':'TST-NEW-BLK','price_kzt':0}).status_code,422)
        response=self.client.post('/api/customers',data={'shop_name':'almaty mobile','contact_name':'Test Person','phone':'+7 700 111 2233'})
        self.assertEqual(response.status_code,409)

    def test_17_stale_report_uses_14_day_threshold(self):
        stale=[o for o in self.client.get('/api/orders').json() if o['stale']]
        self.assertEqual(len(stale),1)
        self.assertEqual(stale[0]['shop_name'],'Tech Corner')

    def test_18_replenishment_includes_unreserved_low_stock(self):
        rows=self.client.get('/api/products').json()
        self.assertTrue(any(p['sku']=='HOC-U72-BLK' and p['reserved']==0 and p['available']<5 for p in rows))

    def test_19_history_is_append_only_and_fk_is_enforced(self):
        with connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE stock_movement SET note='tampered' WHERE movement_id=1")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('DELETE FROM stock_movement WHERE movement_id=1')
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO order_item(order_id,sku,qty_reserved,unit_price_kzt,confirmed_at) VALUES('missing','missing',1,100,'2026-01-01')")

    def test_20_backup_integrity_and_restore_in_isolated_database(self):
        self.order(2)
        backup=create_backup()
        restored=self.folder/'restored.db'
        with closing(sqlite3.connect(backup)) as source,closing(sqlite3.connect(restored)) as destination:
            source.backup(destination)
            self.assertEqual(destination.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(destination.execute("SELECT available FROM inventory WHERE sku='BAS-C65W-WHT'").fetchone()[0],2)

    def test_21_prices_in_old_orders_do_not_change(self):
        oid=self.order(1).json()['order_id']
        with transaction() as db:
            db.execute("UPDATE product SET price_kzt=99999 WHERE sku='BAS-C65W-WHT'")
        order=next(o for o in self.client.get('/api/orders').json() if o['order_id']==oid)
        self.assertEqual(order['total_kzt'],17990)

    def test_22_admin_can_deactivate_user_and_revoke_session(self):
        sales=JsonClient()
        sales.post('/api/auth/login',data={'login':'sales@stockroom.local','password':'Stockroom2026!'})
        self.signin('admin')
        self.assertEqual(self.client.patch('/api/staff/2',data={'role':'sales','is_active':0}).status_code,200)
        self.assertEqual(sales.get('/api/products').status_code,401)
        self.assertEqual(self.client.patch('/api/staff/3',data={'role':'sales','is_active':0}).status_code,409)

    def test_23_cross_origin_write_is_rejected(self):
        response=self.client.post('/api/orders',headers={'Origin':'https://untrusted.example'},data={})
        self.assertEqual(response.status_code,403)

    def test_24_injected_audit_failure_rolls_back_reservation(self):
        with transaction() as db:
            db.execute("CREATE TRIGGER force_audit_failure BEFORE INSERT ON stock_movement BEGIN SELECT RAISE(ABORT,'test audit failure'); END")
        response=self.order(2)
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.product()['reserved'],6)
        with connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],3)

    def test_25_legacy_password_is_upgraded_after_login(self):
        salt=secrets.token_hex(16)
        legacy=salt+':'+hashlib.scrypt(b'Stockroom2026!',salt=salt.encode(),n=16384,r=8,p=1).hex()
        Staff.objects.filter(pk=1).update(password_hash=legacy)
        self.assertEqual(self.signin('manager').status_code,200)
        self.assertTrue(Staff.objects.get(pk=1).password_hash.startswith('scrypt$'))
        self.assertEqual(self.signin('manager').status_code,200)

    def test_26_legacy_session_expiry_is_compared_as_datetime(self):
        token=secrets.token_urlsafe(32)
        with transaction() as db:
            db.execute('INSERT INTO session VALUES(?,?,?)',(token_hash(token),1,(timezone.now()-timedelta(seconds=1)).isoformat()))
        self.client.cookies['stockroom_session']=token
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
        with transaction() as db:
            db.execute('UPDATE session SET expires_at=? WHERE token_hash=?',((timezone.now()+timedelta(hours=1)).isoformat(),token_hash(token)))
        self.assertEqual(self.client.get('/api/auth/me').status_code,200)

    def test_27_malformed_json_and_extra_nested_fields_are_rejected(self):
        for data in ('{', '[]', 'null', '"text"'):
            with self.subTest(data=data):
                self.assertEqual(self.client.post('/api/orders',data=data).status_code,422)
        self.assertEqual(self.client.post('/api/orders',data={'customer_id':1,'channel':'website','lines':[{'sku':'ANK-C20W-WHT','qty':1,'price':1}]}).status_code,422)
        self.assertEqual(self.client.post('/api/orders',data={'customer_id':1,'channel':'website','lines':'[{"sku":"ANK-C20W-WHT","qty":1}]'}).status_code,422)

    def test_28_product_edit_and_customer_creation(self):
        data={'sku':'TST-C20W-BLK','product_name':'Test Charger','brand':'Test','category':'Chargers','price_kzt':1234,'reorder_level':5,'location':'X-01'}
        self.client.post('/api/products',data=data)
        self.assertEqual(self.client.put('/api/products/TST-C20W-BLK',data={**data,'price_kzt':2345}).status_code,200)
        self.assertEqual(self.product('TST-C20W-BLK')['price_kzt'],2345)
        self.assertEqual(self.client.put('/api/products/TST-C20W-BLK',data={**data,'sku':'TST-NEW-BLK'}).status_code,422)
        response=self.client.post('/api/customers',data={'shop_name':'New shop','contact_name':'Test Person','phone':'+7 700 111 2233'})
        self.assertEqual(response.status_code,201)
        self.assertTrue(any(row['customer_id']==response.json()['customer_id'] for row in self.client.get('/api/customers').json()))

    def test_29_backup_download_and_access(self):
        self.assertEqual(self.client.get('/api/backups').status_code,403)
        self.signin('admin')
        response=self.client.post('/api/backups',data={})
        self.assertEqual(response.status_code,201)
        name=response.json()['name']
        self.assertTrue(any(row['name']==name for row in self.client.get('/api/backups').json()))
        response=self.client.get('/api/backups/'+name)
        try:
            self.assertEqual(response.status_code,200)
            self.assertTrue(b''.join(response.streaming_content).startswith(b'SQLite format 3'))
        finally:
            response.close()
        self.assertEqual(self.client.get('/api/backups/no-such-file.db').status_code,400)
        self.assertEqual(self.client.get('/api/backups/stockroom-missing.db').status_code,404)

    def test_30_api_methods_headers_and_frontend_routes(self):
        response=self.client.get('/api/auth/login')
        self.assertEqual(response.status_code,405)
        self.assertEqual(response.headers['Allow'],'POST')
        response=self.client.get('/api/health')
        self.assertEqual(response.json(),{'status':'ok','version':'1.0.0'})
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
        self.assertEqual(self.client.get('/api/unknown').json(),{'detail':'Not found'})

    def test_31_auth_rate_limit(self):
        attempts.clear()
        for _ in range(12):
            self.assertEqual(self.client.post('/api/auth/login',data={'login':'missing@example.test','password':'wrong'}).status_code,401)
        self.assertEqual(self.signin('manager').status_code,429)


if __name__=='__main__':
    unittest.main(verbosity=2)
