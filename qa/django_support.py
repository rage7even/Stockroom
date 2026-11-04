"""Django test client and isolated on-disk databases for transaction/concurrency QA."""
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from django.db import connections
from django.test import Client, override_settings
from backend.db import initialize


class JsonClient(Client):
    def post(self, path, data=None, **kwargs):
        return super().post(path, data=data, content_type='application/json', **kwargs)

    def put(self, path, data=None, **kwargs):
        return super().put(path, data=data, content_type='application/json', **kwargs)

    def patch(self, path, data=None, **kwargs):
        return super().patch(path, data=data, content_type='application/json', **kwargs)


@contextmanager
def isolated_database():
    previous_db = os.environ.get('STOCKROOM_DB')
    previous_demo = os.environ.get('STOCKROOM_DEMO')
    original_name = connections['default'].settings_dict['NAME']
    connections.close_all()
    with tempfile.TemporaryDirectory() as folder:
        path = str(Path(folder) / 'test.db')
        os.environ['STOCKROOM_DB'] = path
        os.environ['STOCKROOM_DEMO'] = '1'
        connections.settings['default']['NAME'] = path
        connections['default'].settings_dict['NAME'] = path
        try:
            with override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1']):
                initialize()
                yield Path(folder)
        finally:
            connections.close_all()
            connections.settings['default']['NAME'] = original_name
            connections['default'].settings_dict['NAME'] = original_name
            for key, value in [('STOCKROOM_DB', previous_db), ('STOCKROOM_DEMO', previous_demo)]:
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
