from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from inventory.models import Staff, Product, Customer, Order, OrderItem
from inventory.services import record


class Command(BaseCommand):
    help = "Create fictional data only on an empty database."

    @transaction.atomic
    def handle(self, *args, **options):
        if Staff.objects.exists():
            self.stdout.write("Demo already initialized. Existing data kept.")
            return
        for role in ["manager", "sales", "admin"]:
            Staff.objects.create_user(
                username=role + "@stockroom.local",
                email=role + "@stockroom.local",
                password="Stockroom2026!",
                full_name=(
                    "Aisulu Manager" if role == "manager" else role.title() + " Demo"
                ),
                role=role,
                is_staff=role == "admin",
                is_superuser=role == "admin",
            )
        manager = Staff.objects.get(role="manager")
        products = [
            (
                "ANK-C20W-WHT",
                "Nano 20W USB-C Charger",
                "Anker",
                "Chargers",
                7990,
                5,
                5,
                "A-01",
            ),
            (
                "BAS-C65W-WHT",
                "GaN 65W Fast Charger",
                "Baseus",
                "Chargers",
                17990,
                10,
                5,
                "A-02",
            ),
            (
                "ANK-PB20-BLK",
                "PowerCore 20000 mAh",
                "Anker",
                "Power banks",
                24990,
                10,
                5,
                "B-01",
            ),
            (
                "SAM-EP45-BLU",
                "Wireless Earphones",
                "Samsung",
                "Audio",
                15990,
                7,
                5,
                "C-01",
            ),
            ("HOC-U72-BLK", "USB-C Cable 1 m", "Hoco", "Cables", 1990, 4, 5, "A-03"),
            (
                "BAS-CBL2-BLK",
                "Braided USB-C Cable 2 m",
                "Baseus",
                "Cables",
                3990,
                36,
                8,
                "A-04",
            ),
            (
                "UGR-HUB7-GRY",
                "7-in-1 USB-C Hub",
                "Ugreen",
                "Adapters",
                22990,
                12,
                4,
                "D-01",
            ),
            (
                "SPG-IP15-CLR",
                "iPhone 15 Clear Case",
                "Spigen",
                "Cases",
                8990,
                28,
                8,
                "E-01",
            ),
            (
                "SPG-IP16-BLK",
                "iPhone 16 Tough Armor",
                "Spigen",
                "Cases",
                12990,
                18,
                5,
                "E-02",
            ),
            (
                "BAS-CAR2-BLK",
                "Dual USB Car Charger",
                "Baseus",
                "Chargers",
                5990,
                3,
                5,
                "A-05",
            ),
            (
                "ANK-MAG5-WHT",
                "Magnetic Wireless Charger",
                "Anker",
                "Chargers",
                13990,
                16,
                5,
                "A-06",
            ),
            (
                "SAM-CBL1-WHT",
                "USB-C to USB-C Cable",
                "Samsung",
                "Cables",
                4990,
                24,
                6,
                "A-07",
            ),
            (
                "UGR-ADP1-GRY",
                "USB-C to HDMI Adapter",
                "Ugreen",
                "Adapters",
                9990,
                9,
                4,
                "D-02",
            ),
            ("HOC-HP10-WHT", "Wired Earphones", "Hoco", "Audio", 2990, 22, 6, "C-02"),
            (
                "BAS-PB10-BLU",
                "Compact Power Bank 10000",
                "Baseus",
                "Power banks",
                11990,
                14,
                5,
                "B-02",
            ),
            (
                "SPG-S24-CLR",
                "Galaxy S24 Clear Case",
                "Spigen",
                "Cases",
                7990,
                0,
                5,
                "E-03",
            ),
            (
                "ANK-C30W-BLK",
                "Nano 30W Charger",
                "Anker",
                "Chargers",
                10990,
                20,
                5,
                "A-08",
            ),
            (
                "UGR-CBL3-GRN",
                "USB-C Cable 3 m",
                "Ugreen",
                "Cables",
                5990,
                15,
                5,
                "A-09",
            ),
        ]

        for sku, name, brand, category, price, qty, threshold, location in products:
            p = Product.objects.create(
                sku=sku,
                product_name=name,
                brand=brand,
                category=category,
                price_kzt=price,
                qty_in_stock=qty,
                reorder_level=threshold,
                location=location,
            )
            if qty:
                record(
                    p,
                    manager,
                    "delivery_in",
                    qty,
                    0,
                    "Opening fictional stock",
                    source="manual",
                )
        for shop in ["Almaty Mobile", "Tech Corner", "City Accessories"]:
            Customer.objects.create(
                shop_name=shop, contact_name="Demo contact", phone="+7 700 000 0000"
            )
        customer = Customer.objects.first()
        for i, (sku, qty) in enumerate(
            [("BAS-C65W-WHT", 6), ("ANK-PB20-BLK", 6), ("SAM-EP45-BLU", 5)], 1
        ):
            order = Order.objects.create(
                order_id=f"ORD-{timezone.now().year}-{i:04d}",
                customer=customer,
                staff=manager,
                channel="sales_manager",
            )
            p = Product.objects.get(pk=sku)
            OrderItem.objects.create(
                order=order, product=p, qty_reserved=qty, unit_price_kzt=p.price_kzt
            )
            record(
                p, manager, "reserve", 0, qty, "Opening fictional reservation", order
            )
            if i == 2:
                Order.objects.filter(pk=order.pk).update(
                    confirmed_at=timezone.now() - timedelta(days=16)
                )
        self.stdout.write(
            "Created 18 products, 3 customers, 3 orders and 3 demo users."
        )
