import logging
from threading import Event, Thread
from django.core.management.commands.runserver import Command as RunserverCommand
from backend.db import initialize
from backend.management.commands.maintenance import run_once

log = logging.getLogger('stockroom')


class Command(RunserverCommand):
    help = 'Run the local Django server with database setup and hourly backup/report checks.'

    def inner_run(self, *args, **options):
        initialize(verbosity=options['verbosity'])
        stop = Event()

        def maintain():
            while not stop.is_set():
                try:
                    run_once()
                except Exception:
                    log.exception('Automatic backup/report check failed')
                stop.wait(3600)

        worker = Thread(target=maintain, name='stockroom-maintenance', daemon=True)
        worker.start()
        try:
            super().inner_run(*args, **options)
        finally:
            stop.set()
            worker.join(timeout=5)
