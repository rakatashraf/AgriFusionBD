"""
Minimal settings for running the *pure* engine tests without GDAL/PostGIS.

The engine (apps/analyses/engine/*) is deliberately ORM-free (plan §4), so it
can be exercised on a settings module that omits ``django.contrib.gis`` and
uses an in-memory SQLite backend. This lets CI validate the science on a
machine that has no GDAL (e.g. the demo laptop before Docker is up).

DB-dependent tests (permissions, idempotency, contract) still run under
``config.settings.dev`` with PostGIS, as required by plan §6.
"""

SECRET_KEY = "engine-test"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

AUTH_USER_MODEL = "auth.User"  # engine tests don't touch the custom user
USE_TZ = True
TIME_ZONE = "Asia/Dhaka"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Engine-only settings the modules read.
POWER_BASE_URL = "https://power.larc.nasa.gov/api"
POWER_TIMEOUT_SECONDS = 10.0
POWER_RETRIES = 3
POWER_CACHE_TTL_SECONDS = 7 * 24 * 3600
HLS_VALID_COVERAGE_MIN = 0.40
