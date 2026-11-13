from django.apps import AppConfig


class RoversConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rovers"
    verbose_name = "Rovers"

    def ready(self):
        # Import the Celery tasks so they are registered whether eager (dev)
        # or running under a worker/beat (prod).
        from . import tasks  # noqa: F401
