# This file has been adapted from add_helsinki_audience.py
from functools import lru_cache

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Event, Keyword, KeywordSet, DataSource

logger = logging.getLogger(__name__)

ESPOO_DATA_SOURCE_ID = 'espoo'

ESPOO_AUDIENCE_KEYWORD_SET_DATA = {
    'id': 'espoo:audiences',
    'name_en': 'Espoo\'s target audiences',
    'name_fi': 'Espoon kohderyhmät',
    'name_sv': 'Esbos målgrupper',
    'data_source_id': ESPOO_DATA_SOURCE_ID,
    'usage': KeywordSet.AUDIENCE,
}

# There are existing YSO keywords for different target audiences (see, e.g., add_helsinki_audience.py). However, the
# Finnish YSO keywords and their translations aren't suitable for Espoo. For instance, there's an existing YSO keyword
# for senior citizens namely YSO keyword p2433. However, Espoo doesn't want to use that YSO keyword since its Finnish
# term is 'ikääntyneet'. Instead, Espoo wants to use 'seniorit' which is the established term that Espoo is using in
# Espoo.fi. The same applies to the other YSO audience keywords and their translations.
#
# We shouldn't solve the issue by renaming any imported YSO keywords in Espoo Events since the master data is YSO. We
# could, however, solve the issue in the frontend by only renaming the YSO keywords there but that wouldn't be optimal
# since then the same hack would need to be implemented in all clients using espooevents-service. Thus, our only option
# seems to be to add new custom keywords with the terms and translations that Espoo wants but this has its own
# drawbacks since, e.g., some of the importers rely on the corresponding YSO keywords. Therefore, we need to make sure
# that any events that have any of the corresponding YSO keywords, e.g., p2433 also get updated with the custom Espoo
# keywords.
#
# Audience keyword ID format: espoo:a<integer>, where a stands for audience followed by a sequential integer
CUSTOM_ESPOO_AUDIENCE_KEYWORDS = [
    {
        'id': 'espoo:a1',
        'name_fi': 'lapsiperheet',
        'name_sv': 'barnfamiljer',
        'name_en': 'families',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:a2',
        'name_fi': 'matkailijat',
        'name_sv': 'besökare',
        'name_en': 'visitors',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:a3',
        'name_fi': 'nuoret',
        'name_sv': 'unga',
        'name_en': 'youth',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:a4',
        'name_fi': 'seniorit',
        'name_sv': 'seniorer',
        'name_en': 'elderly',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
    {
        'id': 'espoo:a5',
        'name_fi': 'vammaiset',
        'name_sv': 'handikappade',
        'name_en': 'disabled',
        'data_source_id': ESPOO_DATA_SOURCE_ID,
    },
]

# A mapping of YSO audience keywords to custom Espoo audience keywords
# Note! If you update any of the YSO keywords here, remember to also update KEYWORDS_TO_ADD_TO_AUDIENCE in
# events/importer/yso.py
YSO_TO_ESPOO_AUDIENCE_KEYWORD_MAPPING = {
    'yso:p13050': 'espoo:a1',  # YSO lapsiperheet -> Espoo lapsiperheet
    'yso:p16596': 'espoo:a2',  # YSO matkailijat -> Espoo matkailijat
    'yso:p11617': 'espoo:a3',  # YSO nuoret -> Espoo nuoret
    'yso:p2433': 'espoo:a4',  # YSO ikääntyneet -> Espoo seniorit
    'yso:p7179': 'espoo:a5',  # YSO vammaiset -> Espoo vammaiset
}


class Command(BaseCommand):
    """Creates a keyword set with Espoo's audiences and maps YSO audience keywords to custom Espoo audience keywords.

    The mapping of the YSO keywords to custom Espoo keywords is done so that any imported events that have any of the
    YSO keywords specified in YSO_TO_ESPOO_AUDIENCE_KEYWORD_MAPPING are also augmented with the corresponding custom
    Espoo audience keywords. Of course, the existing importers could be modified to instead directly add the custom
    Espoo keywords instead of using this management command. However, then we'd need to modify multiple importers and
    the implementations of the existing importers would diverge from the upstream linkedevents repository. This could
    be more fragile since any future updates would need to take these changes into account. By making the update in
    this separate management command, the changes are better isolated from the existing functionality.

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
                logger.info(f"keyword {new_keyword['name_fi']} ({new_keyword['id']}) already exists")

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
            logger.info(f"keyword set \"{ESPOO_AUDIENCE_KEYWORD_SET_DATA['id']}\" already exists")

        # add the keywords to the set
        existing_keywords = set(keyword_set.keywords.all())
        for keyword_dict in CUSTOM_ESPOO_AUDIENCE_KEYWORDS:
            keyword = self._get_keyword_obj(keyword_dict['id'])

            if keyword not in existing_keywords:
                keyword_set.keywords.add(keyword)
                existing_keywords.add(keyword)
                logger.info(f"added {keyword.name} ({keyword_dict['id']}) to the keyword set")

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
        DataSource.objects.get_or_create(id=ESPOO_DATA_SOURCE_ID,
                                         defaults=espoo_data_source_defaults)
        self._create_espoo_audience_keywords()
        self._create_espoo_audiences_keyword_set()
        self._add_espoo_audience_keywords_to_events()
        logger.info('all done')
