from django.apps import AppConfig


class VenusteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "venuste"

    def ready(self):
        import venuste.signals  # noqa: F401
