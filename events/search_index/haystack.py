import logging

from django.apps import apps
from haystack import connections

from events.models import Event, PublicationStatus

logger = logging.getLogger(__name__)


class HaystackSearchIndexService:
    """Service class for managing Haystack search indexes."""

    @classmethod
    def bulk_update_search_indexes(cls, events: list[Event]) -> int:
        """Update Haystack indexes for newly created public events in bulk."""
        if not events:
            return 0

        event_ids = [event.pk for event in events]
        event_queryset = (
            Event.objects.filter(
                pk__in=event_ids,
                publication_status=PublicationStatus.PUBLIC,
                deleted=False,
            )
            .select_related("location")
            .order_by("pk")
        )
        processor = apps.get_app_config("haystack").signal_processor
        backends = processor.connection_router.for_write(instance=events[0])

        for using in backends:
            connection = connections[using]
            index = connection.get_unified_index().get_index(Event)
            connection.get_backend().update(index, event_queryset)

        event_count = event_queryset.count()
        logger.info(f"Haystack index updated for {event_count} Events")
        return event_count
