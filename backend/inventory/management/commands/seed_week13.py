from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import Customer, Order, Staff, Supplier
from inventory.services import Conflict, confirm


class Command(BaseCommand):
    help = "Prepare fictional Week 13 data on a demo database."

    @transaction.atomic
    def handle(self, *args, **options):
        manager = Staff.objects.filter(username="manager@stockroom.local", role="manager").first()
        if manager is None:
            raise CommandError("Run seed and seed_week11 on the demo database first.")

        call_command("seed_week12", stdout=self.stdout)
        supplier = Supplier.objects.get(name="Demo Manufacturer Week 12")
        login = "supplier@stockroom.local"
        representative, created = Staff.objects.get_or_create(
            username=login,
            defaults={"email": login, "full_name": "Demo Supplier", "role": "supplier", "supplier": supplier},
        )
        if created:
            representative.set_password("Stockroom2026!")
            representative.save(update_fields=["password"])
        elif representative.role != "supplier" or representative.supplier_id != supplier.pk:
            raise CommandError("The demo supplier login is already in use.")

        customer = Customer.objects.get(shop_name="Demo Mobile Week 11")
        note = "Week 13 outbound verification demo"
        order = Order.objects.filter(customer=customer, note=note, status__in=["confirmed", "packed"]).first()
        if order is None:
            try:
                order = confirm({
                    "customer": customer, "channel": "website", "note": note,
                    "lines": [{"sku": "DEM-C35W-WHT", "qty": 2}, {"sku": "DEM-CBL2-BLK", "qty": 1}],
                }, manager)
            except Conflict as error:
                raise CommandError(str(error.detail)) from error
        self.stdout.write(f"Outbound demo order: {order.pk}")
        self.stdout.write(f"Purchase chat account: {login}")
