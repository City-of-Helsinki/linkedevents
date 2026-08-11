import logging
from contextlib import contextmanager
from contextvars import ContextVar

from django.conf import settings
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from events.models import Event, Keyword, Place

logger = logging.getLogger(__name__)

_search_index_updates_suppressed = ContextVar(
    "search_index_updates_suppressed", default=False
)


def event_search_index_updates_active() -> bool:
    return settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED and not (
        search_index_updates_suppressed()
    )


def search_index_updates_suppressed() -> bool:
    return _search_index_updates_suppressed.get()


@contextmanager
def suppress_search_index_updates():
    token = _search_index_updates_suppressed.set(True)
    try:
        yield
    finally:
        _search_index_updates_suppressed.reset(token)


@receiver(
    post_save,
    sender=Event,
    dispatch_uid="event_post_save",
)
def event_post_save(sender: type[Event], instance: Event, **kwargs: dict) -> None:
    if event_search_index_updates_active():
        instance.update_search_index()


@receiver(
    post_save,
    sender=Place,
    dispatch_uid="place_post_save",
)
def place_post_save(sender: type[Place], instance: Place, **kwargs: dict) -> None:
    if event_search_index_updates_active():
        for event in instance.events.all():
            event.update_search_index()


@receiver(
    post_save,
    sender=Keyword,
    dispatch_uid="keyword_post_save",
)
def keyword_post_save(sender: type[Keyword], instance: Keyword, **kwargs: dict) -> None:
    if event_search_index_updates_active():
        for event in instance.events.all():
            event.update_search_index()


@receiver(
    m2m_changed,
    sender=Event.keywords.through,
    dispatch_uid="event_keywords_m2m_changed",
)
def event_keywords_m2m_changed(sender, instance, action, **kwargs):
    if event_search_index_updates_active():
        if action in ["post_add", "post_remove", "post_clear"]:
            if isinstance(instance, Event):
                instance.update_search_index()
            if isinstance(instance, Keyword):
                for event in instance.events.all():
                    event.update_search_index()
