import logging
from threading import Event, Thread
from django.core.management import call_command
from django.core.management.commands.runserver import Command as Runserver


class Command(Runserver):
    help = "Local server with an hourly backup check. Use --noreload."

    def inner_run(self, *args, **options):
        stop = Event()

        def maintain():
            while not stop.is_set():
                try:
                    call_command("maintenance", verbosity=0)
                except Exception:
                    logging.exception("Backup/report failed")
                stop.wait(3600)

        worker = Thread(target=maintain, daemon=True)
        worker.start()
        try:
            super().inner_run(*args, **options)
        finally:
            stop.set()
            worker.join(timeout=5)
