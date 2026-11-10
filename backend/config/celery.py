"""Celery app — wired, eager by default (plan §3)."""

import os

import celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = celery.Celery("fieldshift")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
