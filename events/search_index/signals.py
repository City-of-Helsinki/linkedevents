import logging

from django.conf import settings
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from events.models import Event, Keyword, Place

logger = logging.getLogger(__name__)


@receiver(
    post_save,
    sender=Event,
    dispatch_uid="event_post_save",
)
def event_post_save(sender: type[Event], instance: Event, **kwargs: dict) -> None:
    if settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED:
        instance.update_search_index()


@receiver(
    post_save,
    sender=Place,
    dispatch_uid="place_post_save",
)
def place_post_save(sender: type[Place], instance: Place, **kwargs: dict) -> None:
    if settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED:
        for event in instance.events.all():
            event.update_search_index()


@receiver(
    post_save,
    sender=Keyword,
    dispatch_uid="keyword_post_save",
)
def keyword_post_save(sender: type[Keyword], instance: Keyword, **kwargs: dict) -> None:
    if settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED:
        for event in instance.events.all():
            event.update_search_index()


@receiver(
    m2m_changed,
    sender=Event.keywords.through,
    dispatch_uid="event_keywords_m2m_changed",
)
def event_keywords_m2m_changed(sender, instance, action, **kwargs):
    if settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED:
        if action in ["post_add", "post_remove", "post_clear"]:
            if isinstance(instance, Event):
                instance.update_search_index()
            if isinstance(instance, Keyword):
                for event in instance.events.all():
                    event.update_search_index()
