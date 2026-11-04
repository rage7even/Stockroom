import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or secrets.token_urlsafe(48)
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',')
INSTALLED_APPS = ['backend.apps.StockroomConfig']
MIDDLEWARE = ['backend.middleware.RequestGuard']
ROOT_URLCONF = 'backend.urls'
WSGI_APPLICATION = 'backend.wsgi.application'
ASGI_APPLICATION = 'backend.asgi.application'
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': os.environ.get('STOCKROOM_DB', str(BASE_DIR / 'data' / 'stockroom.db')),
    # Lock before reading availability, including with ORM atomic().
    'OPTIONS': {'timeout': 15, 'transaction_mode': 'IMMEDIATE'},
}}
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
USE_TZ = True
TIME_ZONE = 'UTC'
APPEND_SLASH = False
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
PASSWORD_HASHERS = ['django.contrib.auth.hashers.ScryptPasswordHasher']
STOCKROOM_ALLOWED_ORIGINS = os.environ.get(
    'STOCKROOM_ALLOWED_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8000,http://localhost:4200,http://127.0.0.1:4200',
).split(',')
STOCKROOM_SECURE_COOKIE = os.environ.get('STOCKROOM_SECURE_COOKIE') == '1'
