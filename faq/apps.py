from django.apps import AppConfig


class FaqConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "faq"

    def ready(self):
        from . import signals  # noqa: F401  (connects the receivers)
