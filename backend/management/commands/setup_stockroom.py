from django.core.management.base import BaseCommand
from backend.db import initialize


class Command(BaseCommand):
    help = 'Apply migrations, enable WAL and seed fictional data only in an empty database.'

    def handle(self, *args, **options):
        initialize(verbosity=options['verbosity'])
        self.stdout.write(self.style.SUCCESS('Stockroom database is ready. Existing data was preserved.'))
