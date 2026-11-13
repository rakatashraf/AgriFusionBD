"""
Django base settings for FieldShift.

FieldShift — NASA Space Apps 2026 (Bangladesh pilot).
Django is the only authority for authentication, permissions and agronomic
logic (plan §3, report §4). Environment-specific settings live in
``config/settings/dev.py`` and ``config/settings/prod.py``.
"""

from pathlib import Path

from django.contrib import admin as django_admin  # noqa: F401  (referenced by DRF)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = "django-insecure-fieldshift-pilot-do-not-use-in-prod"

DEBUG = False

ALLOWED_HOSTS = ["*"]

# --- Applications -----------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "whitenoise.runserver_nostatic",  # dev: let runserver handle static; prod: whitenoise serves them
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.farms",
    "apps.catalogue",
    "apps.environment",
    "apps.analyses",
    "apps.cases",
    "apps.rovers",
    "apps.research",
    "apps.audit",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serve static/ (and media in prod) without nginx
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Celery app (config/celery.py) — eager by default (plan §3).
from config.celery import app as celery_app  # noqa: E402,F401

# --- Database ---------------------------------------------------------------
# PostgreSQL + PostGIS is the source of truth (plan §3). The default target
# is the Compose service; point DATABASE_URL at a hosted PostGIS when Docker
# is unavailable on the demo laptop.

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "fieldshift",
        "USER": "fieldshift",
        "PASSWORD": "fieldshift",
        "HOST": "127.0.0.1",
        "PORT": "5432",
    }
}

# --- Auth -------------------------------------------------------------------
# Custom email-login user (plan §1, Phase 1).
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

# --- REST framework ----------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Errors use the stable envelope { "error": { code, message, details } }
    # via config/exceptions.py; keep DRF's default renderer set.
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FieldShift API",
    "DESCRIPTION": (
        "Decision-support API for crop-rotation comparison — NASA POWER + HLS "
        "evidence, local soil tests, and a transparent rule engine."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- NASA data layer ---------------------------------------------------------
POWER_BASE_URL = "https://power.larc.nasa.gov/api"
POWER_TIMEOUT_SECONDS = 10.0
POWER_RETRIES = 3
POWER_CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days (plan §3)
HLS_VALID_COVERAGE_MIN = 0.40  # 40 % valid coverage threshold (plan §3)

# --- AgriRover-Q (report §10, plan §5.3) ------------------------------------
# Shared server key compared in constant time. The robot's firmware uses the
# same key (env AGRI_API_KEY, default "dev-key" in the robot's cloud/api.py).
import os as _os
AGRI_API_KEY = _os.environ.get("AGRI_API_KEY", "dev-key")

# --- Celery ------------------------------------------------------------------
# Wired but eager by default so the demo never depends on a broker (plan §3).
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# --- i18n / static / media ----------------------------------------------------
LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- WhiteNoise (static/media serving in production, no nginx) ---------------
# Compress and cache the immutable hashed assets; serve media/ through the same
# middleware so rover images and research exports don't need a separate server.
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = False          # prod: rely on collectstatic + hashed names
WHITENOISE_MIMETYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".map": "application/json",
    ".geojson": "application/geo+json",
    ".json": "application/json",
    ".wasm": "application/wasm",
}
WHITENOISE_MAX_AGE = 60 * 60 * 24 * 365 * 10  # 10 y for content-hashed files
WHITENOISE_COMPRESS = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Security baseline -------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # SPA must read it (plan §1, Phase 1)
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
