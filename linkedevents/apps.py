from django.apps import AppConfig


class LinkedEventsConfig(AppConfig):
    name = "linkedevents"
    verbose_name = "Linked Events"

    def ready(self):
        import events.schema  # noqa
        import helevents.schema  # noqa
        import registrations.schema  # noqa
