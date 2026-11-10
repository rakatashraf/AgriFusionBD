from django.apps import AppConfig


class AnalysesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analyses"
    verbose_name = "Analyses"

    def ready(self):
        # Import the task so Celery picks it up when eager or under a worker.
        from . import tasks  # noqa: F401
