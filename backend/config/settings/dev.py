"""Development settings — permissive for the single-origin demo setup.

Reads from environment so the Compose stack and a hosted PostGIS both work
(plan §3, §8). Falls back to sane 127.0.0.1 defaults.
"""

import os
from urllib.parse import urlparse

from .base import *  # noqa: F403

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

# --- Database ----------------------------------------------------------------
def _database():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        u = urlparse(db_url if "://" in db_url else "postgres://" + db_url)
        return {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": u.path.lstrip("/"),
            "USER": u.username,
            "PASSWORD": u.password,
            "HOST": u.hostname,
            "PORT": str(u.port or 5432),
        }
    return {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("POSTGRES_DB", "fieldshift"),
        "USER": os.environ.get("POSTGRES_USER", "fieldshift"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "fieldshift"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }

DATABASES = {"default": _database()}

# --- Celery (eager by default) ----------------------------------------------
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "1") == "1"
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# --- CORS --------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()
]
