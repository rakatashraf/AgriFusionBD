"""Production settings — strict cookies, TLS-terminated behind nginx."""

from .base import *  # noqa: F403

DEBUG = False

ALLOWED_HOSTS = [
    "pilot.fieldshift.example",
    "localhost",
    "127.0.0.1",
]

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
