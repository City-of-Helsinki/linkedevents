import logging

from django.core.management.base import BaseCommand

from events.models import Event, EventSearchIndex, EventSearchIndexService

logger = logging.getLogger(__name__)


def rebuild_event_search_index() -> int:
    """
    Rebuild the full text search index for the events.

    This function iterates through all events, extracts words from the specified
    columns, and updates the EventSearchIndex model with data for
    the specified language.

    :return: The number of updated search objects.
    """
    num_updated = 0
    qs = Event.objects.all().order_by("pk")
    for event in qs.iterator(chunk_size=10000):
        event.update_search_index()
        num_updated += 1
    return num_updated


class Command(BaseCommand):
    help = "Rebuilds the search vectors for the full text search objects."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Clean the search index before rebuilding.",
        )

    def handle(self, *args, **options):
        if options["clean"]:
            logger.info("Cleaning the search index.")
            EventSearchIndex.objects.all().delete()
            logger.info("Cleaned the search index.")
        logger.info("Rebuilding event search index...")
        num_updated = rebuild_event_search_index()
        logger.info(f"Search index updated for {num_updated} Events")
        EventSearchIndexService.update_index_search_vectors()
