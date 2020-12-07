# This file has been adapted from add_helsinki_audience.py
from functools import lru_cache

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Keyword, KeywordSet, DataSource

logger = logging.getLogger(__name__)

ESPOO_KEYWORD_SET_DATA = {
    'id': 'espoo:audiences',
    'name_en': 'Espoo\'s target audiences',
    'name_fi': 'Espoon kohderyhmät',
    'name_sv': 'Esbos målgrupper',
    'data_source_id': 'espoo',
    'usage': KeywordSet.AUDIENCE,
}

# Note! If you update any of the keywords here, remember to also update KEYWORDS_TO_ADD_TO_AUDIENCE in
# events/importer/yso.py
KEYWORD_IDS = [
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
NEW_ESPOO_KEYWORDS = [
    {
        'id': 'espoo:a1',
        'name_fi': 'seniorit',
        'name_sv': 'seniorer',
        'name_en': 'senior citizens',
        'data_source_id': 'espoo',
    }
]


class Command(BaseCommand):
    help = "Creates a keyword set with Espoo's target audiences."

    @lru_cache()
    def get_keyword_obj(self, keyword_id):
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            raise CommandError('keyword "{}" does not exist'.format(keyword_id))
        return keyword

    @transaction.atomic()
    def create_espoo_keywords(self):
        logger.info('creating new Espoo keywords...')

        for new_keyword in NEW_ESPOO_KEYWORDS:
            keyword_set, created = Keyword.objects.update_or_create(
                id=new_keyword['id'],
                defaults=new_keyword
            )
            if created:
                logger.info('created keyword {} ({})'.format(new_keyword['name_fi'], new_keyword['id']))
            else:
                logger.info('keyword {} ({}) already exist'.format(new_keyword['name_fi'], new_keyword['id']))

    @transaction.atomic()
    def create_espoo_audiences_keyword_set(self):
        logger.info('creating Espoo target audiences keyword set...')

        # create the set itself
        keyword_set, created = KeywordSet.objects.update_or_create(
            id=ESPOO_KEYWORD_SET_DATA['id'],
            defaults=ESPOO_KEYWORD_SET_DATA
        )
        if created:
            logger.info('created keyword set "{}"'.format(ESPOO_KEYWORD_SET_DATA['id']))
        else:
            logger.info('keyword set "{}" already exist'.format(ESPOO_KEYWORD_SET_DATA['id']))

        # add the keywords to the set
        existing_keywords = set(keyword_set.keywords.all())
        for keyword_id in KEYWORD_IDS:
            keyword = self.get_keyword_obj(keyword_id)

            if keyword not in existing_keywords:
                keyword_set.keywords.add(keyword)
                existing_keywords.add(keyword)
                logger.info('added {} ({}) to the keyword set'.format(keyword.name, keyword_id))

    def handle(self, *args, **options):
        # Espoo data source must be created if missing. Note that it is not necessarily the system data source.
        # If we are creating it, it *may* still be the system data source, so it must be user editable!
        espoo_data_source_defaults = {'user_editable': True}
        DataSource.objects.get_or_create(id=ESPOO_KEYWORD_SET_DATA['data_source_id'],
                                         defaults=espoo_data_source_defaults)
        self.create_espoo_keywords()
        self.create_espoo_audiences_keyword_set()
        logger.info('all done')
