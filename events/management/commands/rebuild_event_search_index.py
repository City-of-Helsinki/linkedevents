import logging

from django.core.management.base import BaseCommand

from events.models import EventSearchIndex
from events.search_index.postgres import EventSearchIndexService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rebuilds the search vectors for the full text search objects."

    def handle(self, *args, **options):
        logger.info("Cleaning the search index...")
        EventSearchIndex.objects.all().delete()
        logger.info("Cleaned the search index.")
        EventSearchIndexService.bulk_update_search_indexes()
        EventSearchIndexService.update_index_search_vectors()
