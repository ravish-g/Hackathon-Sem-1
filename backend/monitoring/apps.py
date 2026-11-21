from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.monitoring"

    def ready(self):
        from . import activity  # Register event-log listeners.
