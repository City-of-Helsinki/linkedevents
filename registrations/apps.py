from django.apps import AppConfig


class RegistrationsConfig(AppConfig):
    name = "registrations"

    def ready(self):
        import registrations.signals  # noqa
