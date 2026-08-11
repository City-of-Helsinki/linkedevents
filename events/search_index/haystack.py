import logging

from django.apps import apps
from haystack import connections
from haystack.signals import RealtimeSignalProcessor

from events.models import Event, PublicationStatus
from events.search_index.signals import search_index_updates_suppressed

logger = logging.getLogger(__name__)


class ScopedRealtimeSignalProcessor(RealtimeSignalProcessor):
    """Skip Haystack realtime updates only inside a bulk operation."""

    def handle_save(self, sender, instance, **kwargs):
        if search_index_updates_suppressed():
            return
        return super().handle_save(sender, instance, **kwargs)

    def handle_delete(self, sender, instance, **kwargs):
        if search_index_updates_suppressed():
            return
        return super().handle_delete(sender, instance, **kwargs)


class HaystackSearchIndexService:
    """Service class for managing Haystack search indexes."""

    @classmethod
    def bulk_update_search_indexes(cls, events: list[Event]) -> int:
        """Update or remove supplied events in Haystack indexes in bulk."""
        if not events:
            return 0

        event_ids = [event.pk for event in events]
        event_queryset = (
            Event.objects.filter(pk__in=event_ids)
            .select_related("location")
            .order_by("pk")
        )
        public_event_queryset = event_queryset.filter(
            publication_status=PublicationStatus.PUBLIC,
            deleted=False,
        )
        events_to_remove = event_queryset.exclude(
            publication_status=PublicationStatus.PUBLIC,
            deleted=False,
        )
        processor = apps.get_app_config("haystack").signal_processor
        backends = processor.connection_router.for_write(instance=events[0])

        for using in backends:
            connection = connections[using]
            index = connection.get_unified_index().get_index(Event)
            backend = connection.get_backend()
            backend.update(index, public_event_queryset)
            for event in events_to_remove:
                backend.remove(event)

        event_count = public_event_queryset.count()
        logger.info(
            "Haystack index updated for %s public Events and removed %s "
            "non-public or deleted Events",
            event_count,
            len(events_to_remove),
        )
        return event_count
