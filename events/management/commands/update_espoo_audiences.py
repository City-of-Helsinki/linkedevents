from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from functools import lru_cache
import logging

from events.models import Event, Keyword

logger = logging.getLogger(__name__)

# For more information regarding the custom Espoo audience keywords, see add_espoo_audience.py
YSO_TO_ESPOO_KEYWORD_MAPPING = {
    'yso:p2433': ['espoo:a1'],  # ikääntyneet -> seniorit
}


class Command(BaseCommand):
    """Maps YSO audience keywords to custom Espoo audience keywords.

    This should be run so that any imported events that have any of the YSO keywords specified in
    YSO_TO_ESPOO_KEYWORD_MAPPING are also augmented with the custom Espoo audience keywords. Of course, the existing
    importers could be modified to instead use the custom Espoo keywords instead of using this management command.
    However, then we'd need to modify multiple importers and the implementations of the existing importers would
    diverge from the upstream linkedevents repository. This could be more fragile since any future updates would need
    to take these changes into account. By making the update in this separate management command, the changes are
    better isolated from existing functionality.

    Since some of the importers are run hourly, this management command should also be run hourly.

    Note also that this management command should be run after the add_espoo_audience management command.

    This management command could probably be combined with add_espoo_audience.py to simplify the setup. For now, it's
    separate since the responsibility of this management command is not to add a keyword set but to only update events
    with the custom Espoo audience keywords. However, this could be circumvented by using command arguments.
    """
    help = "Map YSO audience keywords to custom Espoo audience keywords (this is meant to be run hourly)"

    @lru_cache()
    def get_keyword_obj(self, keyword_id):
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            raise CommandError('keyword "{}" does not exist'.format(keyword_id))
        return keyword

    @transaction.atomic()
    def add_espoo_audience_keywords_to_events(self):
        logger.info('Adding Espoo audience keywords to events...')

        for event in Event.objects.exclude(audience__isnull=True).prefetch_related('audience'):
            for audience in event.audience.all():

                # Map the given YSO audience keywords to custom Espoo audience keywords
                for espoo_keyword_id in YSO_TO_ESPOO_KEYWORD_MAPPING.get(audience.id, []):
                    espoo_keyword_obj = self.get_keyword_obj(espoo_keyword_id)

                    if espoo_keyword_obj not in event.audience.all():
                        event.audience.add(espoo_keyword_obj)
                        logger.info('added {} ({}) to {}'.format(espoo_keyword_obj, espoo_keyword_id, event))

    def handle(self, **kwargs):
        self.add_espoo_audience_keywords_to_events()
        logger.info('Finished mapping YSO audience keywords to custom Espoo audience keywords')
