import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from events.models import EventSearchIndex
from events.search_index.postgres import EventSearchIndexService
from events.search_index.utils import batch_qs

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rebuilds the search vectors for the full text search objects."

    def handle(self, *args, **options):
        logger.info("Cleaning the search index...")
        self.delete_index_in_batches()
        EventSearchIndexService.bulk_update_search_indexes()
        EventSearchIndexService.update_index_search_vectors()

    @transaction.atomic
    def delete_index_in_batches(self):
        for _, _, _, qs in batch_qs(
            EventSearchIndex.objects.all(),
            batch_size=settings.EVENT_SEARCH_INDEX_REBUILD_BATCH_SIZE,
        ):
            ids = qs.values_list("event_id", flat=True)
            EventSearchIndex.objects.filter(event_id__in=ids).delete()
