# This file has been adapted from add_helsinki_audience.py
from functools import lru_cache

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Event, Keyword, KeywordSet, DataSource

logger = logging.getLogger(__name__)

ESPOO_AUDIENCE_KEYWORD_SET_DATA = {
    'id': 'espoo:audiences',
    'name_en': 'Espoo\'s target audiences',
    'name_fi': 'Espoon kohderyhmät',
    'name_sv': 'Esbos målgrupper',
    'data_source_id': 'espoo',
    'usage': KeywordSet.AUDIENCE,
}

# Note! If you update any of the keywords here, remember to also update KEYWORDS_TO_ADD_TO_AUDIENCE in
# events/importer/yso.py
AUDIENCE_KEYWORD_IDS = [
    'yso:p13050',  # lapsiperheet
    'yso:p16596',  # matkailijat
    'yso:p11617',  # nuoret
    'espoo:a1',  # seniorit
    'yso:p7179',  # vammaiset
]

# There's an existing YSO keyword for senior citizens namely YSO keyword p2433. However, Espoo doesn't want to use the
# YSO keyword since its Finnish term is 'ikääntyneet'. Instead, Espoo wants to use 'seniorit' which is the established
# term that Espoo is using in Espoo.fi. To solve the issue, we shouldn't rename any imported YSO keywords in Espoo
# Events since the master data is YSO. We could solve the issue in the frontend by only renaming the YSO keyword there
# but that wouldn't be optimal since then the same hack would need to be implemented in all clients using
# espooevents-service. Thus, our only option seems to be to add a new custom keyword with the Finnish term that Espoo
# wants but this has its own drawbacks since, e.g., some of the importers rely on the p2433 keyword. Therefore, we need
# to make sure that any events that have the p2433 keyword also get updated with the custom Espoo keyword.
# Audience keyword ID format: espoo:a<integer>, where a stands for audience followed by a sequential integer
CUSTOM_ESPOO_AUDIENCE_KEYWORDS = [
    {
        'id': 'espoo:a1',
        'name_fi': 'seniorit',
        'name_sv': 'seniorer',
        'name_en': 'senior citizens',
        'data_source_id': 'espoo',
    }
]

# A mapping of YSO audience keywords to custom Espoo audience keywords
YSO_TO_ESPOO_AUDIENCE_KEYWORD_MAPPING = {
    'yso:p2433': 'espoo:a1',  # ikääntyneet -> seniorit
}


class Command(BaseCommand):
    """Creates a keyword set with Espoo's audiences and maps YSO audience keywords to custom Espoo audience keywords.

    The mapping of YSO keywords to custom Espoo keywords is done so that any imported events that have any of the YSO
    keywords specified in YSO_TO_ESPOO_AUDIENCE_KEYWORD_MAPPING are also augmented with the custom Espoo audience
    keywords. Of course, the existing importers could be modified to instead directly add the custom Espoo keywords
    instead of using this management command. However, then we'd need to modify multiple importers and the
    implementations of the existing importers would diverge from the upstream linkedevents repository. This could be
    more fragile since any future updates would need to take these changes into account. By making the update in this
    separate management command, the changes are better isolated from existing functionality.

    Since some of the importers are run hourly, this management command should also be run hourly so that any imported
    events get augmented with the custom Espoo audience keywords.
    """
    help = (
     "Creates a keyword set with Espoo's target audiences and maps YSO audience keywords to custom Espoo audience "
     "keywords (this is meant to be run hourly)."
    )

    @lru_cache()
    def _get_keyword_obj(self, keyword_id):
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            raise CommandError(f"keyword \"{keyword_id}\" does not exist")
        return keyword

    @transaction.atomic()
    def _create_espoo_audience_keywords(self):
        logger.info('creating new Espoo audience keywords...')

        for new_keyword in CUSTOM_ESPOO_AUDIENCE_KEYWORDS:
            keyword_set, created = Keyword.objects.update_or_create(
                id=new_keyword['id'],
                defaults=new_keyword
            )
            if created:
                logger.info(f"created keyword {new_keyword['name_fi']} ({new_keyword['id']})")
            else:
                logger.info(f"keyword {new_keyword['name_fi']} ({new_keyword['id']}) already exist")

    @transaction.atomic()
    def _create_espoo_audiences_keyword_set(self):
        logger.info('creating Espoo audiences keyword set...')

        # create the set itself
        keyword_set, created = KeywordSet.objects.update_or_create(
            id=ESPOO_AUDIENCE_KEYWORD_SET_DATA['id'],
            defaults=ESPOO_AUDIENCE_KEYWORD_SET_DATA
        )
        if created:
            logger.info(f"created keyword set \"{ESPOO_AUDIENCE_KEYWORD_SET_DATA['id']}\"")
        else:
            logger.info(f"keyword set \"{ESPOO_AUDIENCE_KEYWORD_SET_DATA['id']}\" already exist")

        # add the keywords to the set
        existing_keywords = set(keyword_set.keywords.all())
        for keyword_id in AUDIENCE_KEYWORD_IDS:
            keyword = self._get_keyword_obj(keyword_id)

            if keyword not in existing_keywords:
                keyword_set.keywords.add(keyword)
                existing_keywords.add(keyword)
                logger.info(f"added {keyword.name} ({keyword_id}) to the keyword set")

    @transaction.atomic()
    def _add_espoo_audience_keywords_to_events(self):
        logger.info('adding Espoo audience keywords to events...')

        for event in Event.objects.exclude(audience__isnull=True).prefetch_related('audience'):
            for audience in event.audience.all():

                if audience.id not in YSO_TO_ESPOO_AUDIENCE_KEYWORD_MAPPING:
                    continue

                # Map the given YSO audience keyword to a custom Espoo audience keyword
                espoo_keyword_id = YSO_TO_ESPOO_AUDIENCE_KEYWORD_MAPPING.get(audience.id)
                espoo_keyword_obj = self._get_keyword_obj(espoo_keyword_id)

                if espoo_keyword_obj not in event.audience.all():
                    event.audience.add(espoo_keyword_obj)
                    logger.info(f"added {espoo_keyword_obj} ({espoo_keyword_id}) to {event}")

    def handle(self, *args, **options):
        # Espoo data source must be created if missing. Note that it is not necessarily the system data source.
        # If we are creating it, it *may* still be the system data source, so it must be user editable!
        espoo_data_source_defaults = {'user_editable': True}
        DataSource.objects.get_or_create(id=ESPOO_AUDIENCE_KEYWORD_SET_DATA['data_source_id'],
                                         defaults=espoo_data_source_defaults)
        self._create_espoo_audience_keywords()
        self._create_espoo_audiences_keyword_set()
        self._add_espoo_audience_keywords_to_events()
        logger.info('all done')
