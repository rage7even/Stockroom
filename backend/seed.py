"""Fictional demo data; seed only an empty staff table, never reset existing records."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from backend.models import Staff, Product, Customer, Order, OrderItem, StockMovement
from backend.security import hash_password

PRODUCTS = [('ANK-C20W-WHT', 'Nano 20W USB-C Charger', 'Anker', 'Chargers', 7990, 5, 5, 'A-01'),
 ('BAS-C65W-WHT', 'GaN 65W Fast Charger', 'Baseus', 'Chargers', 17990, 10, 5, 'A-02'),
 ('ANK-PB20-BLK', 'PowerCore 20000 mAh', 'Anker', 'Power banks', 24990, 10, 5, 'B-01'),
 ('SAM-EP45-BLU', 'Wireless Earphones', 'Samsung', 'Audio', 15990, 7, 5, 'C-01'),
 ('HOC-U72-BLK', 'USB-C Cable 1 m', 'Hoco', 'Cables', 1990, 4, 5, 'A-03'),
 ('BAS-CBL2-BLK', 'Braided USB-C Cable 2 m', 'Baseus', 'Cables', 3990, 36, 8, 'A-04'),
 ('UGR-HUB7-GRY', '7-in-1 USB-C Hub', 'Ugreen', 'Adapters', 22990, 12, 4, 'D-01'),
 ('SPG-IP15-CLR', 'iPhone 15 Clear Case', 'Spigen', 'Cases', 8990, 28, 8, 'E-01'),
 ('SPG-IP16-BLK', 'iPhone 16 Tough Armor', 'Spigen', 'Cases', 12990, 18, 5, 'E-02'),
 ('BAS-CAR2-BLK', 'Dual USB Car Charger', 'Baseus', 'Chargers', 5990, 3, 5, 'A-05'),
 ('ANK-MAG5-WHT', 'Magnetic Wireless Charger', 'Anker', 'Chargers', 13990, 16, 5, 'A-06'),
 ('SAM-CBL1-WHT', 'USB-C to USB-C Cable', 'Samsung', 'Cables', 4990, 24, 6, 'A-07'),
 ('UGR-ADP1-GRY', 'USB-C to HDMI Adapter', 'Ugreen', 'Adapters', 9990, 9, 4, 'D-02'),
 ('HOC-HP10-WHT', 'Wired Earphones', 'Hoco', 'Audio', 2990, 22, 6, 'C-02'),
 ('BAS-PB10-BLU', 'Compact Power Bank 10000', 'Baseus', 'Power banks', 11990, 14, 5, 'B-02'),
 ('SPG-S24-CLR', 'Galaxy S24 Clear Case', 'Spigen', 'Cases', 7990, 0, 5, 'E-03'),
 ('ANK-C30W-BLK', 'Nano 30W Charger', 'Anker', 'Chargers', 10990, 20, 5, 'A-08'),
 ('UGR-CBL3-GRN', 'USB-C Cable 3 m', 'Ugreen', 'Cables', 5990, 15, 5, 'A-09')]

@transaction.atomic
def seed_demo():
    if Staff.objects.exists():
        return
    for name, login, role in [('Aisulu Manager','manager@stockroom.local','manager'), ('Sales Demo','sales@stockroom.local','sales'), ('Admin Demo','admin@stockroom.local','admin')]:
        Staff.objects.create(full_name=name, login=login, role=role, password_hash=hash_password('Stockroom2026!'))
    opening = timezone.now() - timedelta(days=30)
    for sku, name, brand, category, price, qty, reorder, location in PRODUCTS:
        Product.objects.create(sku=sku, product_name=name, brand=brand, category=category, price_kzt=price,
                               qty_in_stock=qty, reorder_level=reorder, location=location)
        if qty:
            StockMovement.objects.create(sku_id=sku, movement_type='delivery_in', physical_delta=qty,
                                         moved_at=opening, staff_id=1, source='manual', note='Opening demo stock вЂ” fictional data')
    for shop, name, phone in [('Almaty Mobile','Demo contact A','+7 700 000 0001'), ('Tech Corner','Demo contact B','+7 700 000 0002'), ('City Accessories','Demo contact C','+7 700 000 0003')]:
        Customer.objects.create(shop_name=shop, contact_name=name, phone=phone)
    for num, customer, sku, qty, age in [(1,1,'BAS-C65W-WHT',6,0), (2,2,'ANK-PB20-BLK',6,16), (3,3,'SAM-EP45-BLU',5,1)]:
        stamp = timezone.now() - timedelta(days=age)
        order = Order.objects.create(order_id=f'ORD-{timezone.now().year}-{num:04d}', customer_id=customer,
                                     channel='sales_manager', status='confirmed', confirmed_at=stamp, updated_at=stamp,
                                     staff_id=2, note='Fictional demonstration order')
        price = Product.objects.get(pk=sku).price_kzt
        OrderItem.objects.create(order=order, sku_id=sku, qty_reserved=qty, unit_price_kzt=price, confirmed_at=stamp)
        StockMovement.objects.create(sku_id=sku, movement_type='reserve', reserved_delta=qty,
                                     moved_at=stamp, staff_id=2, order=order, source='system', note='Opening demo reservation')
