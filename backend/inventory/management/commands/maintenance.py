import csv
import sqlite3
from pathlib import Path
from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from inventory.models import Order


class Command(BaseCommand):
    help = "Create a verified daily backup and a stale-reservation report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-backup", action="store_true", help="Create a snapshot immediately."
        )

    def handle(self, *args, **options):
        folder = Path(settings.DATABASES["default"]["NAME"]).parent / "backups"
        folder.mkdir(exist_ok=True)
        files = sorted(folder.glob("stockroom-*.db"))
        backup_due = not files or timezone.now().timestamp() - files[-1].stat().st_mtime > 86400
        if options["force_backup"] or backup_due:
            target = folder / (
                "stockroom-" + timezone.now().strftime("%Y%m%d-%H%M%S-%f") + ".db"
            )
            with sqlite3.connect(
                settings.DATABASES["default"]["NAME"]
            ) as source, sqlite3.connect(target) as copy:
                source.backup(copy)
                if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup failed integrity check")
            for old in sorted(folder.glob("stockroom-*.db"))[:-30]:
                old.unlink()
            self.stdout.write(f"Backup created: {target}")
        rows = Order.objects.filter(
            status__in=["confirmed", "packed"],
            confirmed_at__lt=timezone.now() - timedelta(days=14),
        ).select_related("customer")
        with (folder.parent / "stale_reservations.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["Order", "Shop", "Confirmed UTC"])
            for o in rows:
                writer.writerow(
                    [o.pk, o.customer.shop_name, o.confirmed_at.isoformat()]
                )
