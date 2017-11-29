from django.apps import AppConfig
from django.db.models.signals import post_save

from .signals import organization_post_save


class EventsConfig(AppConfig):
    name = 'events'

    def ready(self):
        post_save.connect(
            organization_post_save,
            sender="django_orghierarchy.Organization",
            dispatch_uid='organization_post_save',
        )
