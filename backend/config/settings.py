from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "stockroom-local-study-project-change-before-hosting"
)
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
ALLOWED_HOSTS += [
    host.strip() for host in os.environ.get("STOCKROOM_EXTRA_HOSTS", "").split(",")
    if host.strip()
]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "inventory",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("STOCKROOM_DB", str(BASE_DIR / "stockroom.db")),
        "OPTIONS": {"timeout": 15, "transaction_mode": "IMMEDIATE"},
    }
}
AUTH_USER_MODEL = "inventory.Staff"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": ["inventory.permissions.StockroomAccess"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
CSRF_TRUSTED_ORIGINS = ["http://localhost:4200", "http://127.0.0.1:4200"]
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
USE_TZ = True
TIME_ZONE = "Asia/Almaty"
STATIC_URL = "/static/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 28800
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_BACKEND = os.environ.get("STOCKROOM_EMAIL_BACKEND") or (
    "inventory.mail_backend.ResendBackend" if RESEND_API_KEY else "django.core.mail.backends.smtp.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.environ.get("STOCKROOM_EMAIL_FROM", "Stockroom <stockroom@localhost>")
EMAIL_HOST = os.environ.get("STOCKROOM_SMTP_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("STOCKROOM_SMTP_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("STOCKROOM_SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("STOCKROOM_SMTP_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("STOCKROOM_SMTP_TLS") == "true"
EMAIL_USE_SSL = os.environ.get("STOCKROOM_SMTP_SSL") == "true"
EMAIL_TIMEOUT = 10

if os.environ.get("RENDER") == "true":
    DEBUG = False
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])
    CSRF_TRUSTED_ORIGINS.append(os.environ["RENDER_EXTERNAL_URL"])
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
