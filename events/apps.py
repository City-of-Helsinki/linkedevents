from django.apps import AppConfig


class EventsConfig(AppConfig):
    name = "events"

    def ready(self):
        import events.signals  # noqa
        import events.search_index.signals  # noqa
