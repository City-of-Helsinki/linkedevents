import logging
from django.core.management import BaseCommand
from events.models import Keyword, Place

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Update keyword has_upcoming_events field"

    def handle(self, **kwargs):
        Keyword.objects.has_upcoming_events_update()
        Place.upcoming_events.has_upcoming_events_update()
        logger.info('has_upcoming_events for Keywords and Places updated.')
