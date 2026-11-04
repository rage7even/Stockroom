from django.core.management.base import BaseCommand
from backend.backup import backup_if_due
from backend.reports import write_stale_report_if_due


def run_once():
    backup_if_due()
    write_stale_report_if_due()


class Command(BaseCommand):
    help = 'Check the daily backup and stale reservation CSV once (also suitable for a scheduler).'

    def handle(self, *args, **options):
        run_once()
        self.stdout.write('Maintenance complete.')
