from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import Customer, Order, Product, Staff
from inventory.services import confirm, record, transition


class Command(BaseCommand):
    help = "Add fictional week 11 products and a shipped return demonstration order."

    def add_arguments(self, parser):
        parser.add_argument(
            "--catalogue", action="store_true",
            help="Also add 100 fictional catalogue products (safe to repeat).",
        )
        parser.add_argument(
            "--if-demo", action="store_true",
            help="Skip databases without the demo manager account.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        staff = Staff.objects.filter(username="manager@stockroom.local", role="manager").first()
        if staff is None:
            if options["if_demo"]:
                self.stdout.write("Week 11 seed skipped: demo manager account is absent.")
                return
            raise CommandError("Run seed on an empty demo database first.")

        for sku, name, category, price in (
            ("DEM-C35W-WHT", "Demo 35W USB-C Charger", "Chargers", 7990),
            ("DEM-CBL2-BLK", "Demo USB-C Cable 2 m", "Cables", 2990),
            ("DEM-PB10-GRY", "Demo 10000 mAh Power Bank", "Power banks", 11990),
        ):
            product, created = Product.objects.get_or_create(
                sku=sku,
                defaults=dict(
                    product_name=name, brand="Stockroom Demo", category=category,
                    price_kzt=price, qty_in_stock=12, reorder_level=4, location="DEMO-A",
                ),
            )
            if created:
                record(product, staff, "delivery_in", 12, 0, "Week 11 demo stock")

        customer, _ = Customer.objects.get_or_create(
            shop_name="Demo Mobile Week 11",
            defaults={"contact_name": "Demo contact", "phone": "+7 700 000 0011"},
        )
        for username, name, role, shop in (
            ("shop", "Demo Mobile Sales", "sales", customer),
            ("support", "Demo Tech Support", "tech_support", None),
        ):
            login = f"{username}@stockroom.local"
            if not Staff.objects.filter(username=login).exists():
                Staff.objects.create_user(
                    username=login, email=login, full_name=name, role=role,
                    shop=shop, password="Stockroom2026!",
                )
        marker = "Week 11 return demo"
        order = Order.objects.filter(customer=customer, note=marker).first()
        if order is None:
            order = confirm({
                "customer": customer, "channel": "sales_manager", "note": marker,
                "lines": [{"sku": "DEM-C35W-WHT", "qty": 5}],
            }, staff)
            transition(order.pk, "ship", staff)
        if options["catalogue"]:
            self.add_catalogue(staff)
        self.stdout.write(f"Week 11 return demo order: {order.pk}")

    def add_catalogue(self, staff):
        categories = (
            ("Chargers", "USB-C charger", 4990),
            ("Cables", "Braided USB cable", 1790),
            ("Cases", "Protective phone case", 2490),
            ("Power banks", "Portable power bank", 8990),
            ("Audio", "Wired earphones", 3290),
            ("Adapters", "USB-C adapter", 2990),
        )
        added = 0
        for number in range(1, 101):
            category, name, price = categories[(number - 1) % len(categories)]
            quantity = number % 25
            product, created = Product.objects.get_or_create(
                sku=f"LAB-D{number:03d}-STD",
                defaults={
                    "product_name": f"{name} Demo {number:03d}",
                    "brand": "Stockroom Lab",
                    "category": category,
                    "price_kzt": price + 100 * (number % 10),
                    "qty_in_stock": quantity,
                    "reorder_level": 5,
                    "location": f"LAB-{(number - 1) // 10 + 1:02d}",
                },
            )
            if created:
                added += 1
                if quantity:
                    record(product, staff, "delivery_in", quantity, 0, "Demo catalogue opening stock")
        self.stdout.write(f"Demo catalogue: {added} new products; {Product.objects.count()} total.")
