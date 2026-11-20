from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import Product, Staff, Supplier, SupplierOffer
from inventory.purchases import place_purchase


class Command(BaseCommand):
    help = "Add a fictional supplier and a 10-unit purchase for the Week 12 demonstration."

    @transaction.atomic
    def handle(self, *args, **options):
        staff = Staff.objects.filter(username="manager@stockroom.local", role="manager").first()
        products = Product.objects.in_bulk(["DEM-C35W-WHT", "DEM-CBL2-BLK", "DEM-PB10-GRY"])
        if staff is None or len(products) != 3:
            raise CommandError("Run seed and seed_week11 on the demo database first.")

        supplier, _ = Supplier.objects.get_or_create(
            name="Demo Manufacturer Week 12",
            defaults={
                "location": "Almaty, Kazakhstan", "agreement": "Fictional course demonstration",
                "agreement_active": True, "lead_days": 5,
            },
        )
        for sku, cost, qty in (
            ("DEM-C35W-WHT", 5200, 35), ("DEM-CBL2-BLK", 1400, 50), ("DEM-PB10-GRY", 7300, 0),
        ):
            SupplierOffer.objects.get_or_create(
                supplier=supplier, product=products[sku],
                defaults={"unit_cost": cost, "available_qty": qty},
            )

        order = supplier.purchaseorder_set.order_by("pk").first()
        if order is None:
            order = place_purchase({
                "supplier_id": supplier.pk,
                "lines": [{"sku": "DEM-C35W-WHT", "qty": 10}],
            }, staff)
        self.stdout.write(f"Week 12 demo purchase: PO-{order.pk} · barcode SR-DEM-C35W-WHT")
