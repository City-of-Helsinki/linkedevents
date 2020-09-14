from django.apps import AppConfig
from django.db.models.signals import post_save


class EventsConfig(AppConfig):
    name = 'events'

    def ready(self):
        from .signals import organization_post_save, user_post_save
        from django.contrib.auth import get_user_model
        post_save.connect(
            organization_post_save,
            sender="django_orghierarchy.Organization",
            dispatch_uid='organization_post_save',
        )
        post_save.connect(
            user_post_save,
            sender=get_user_model(),
            dispatch_uid='user_post_save',
        )
