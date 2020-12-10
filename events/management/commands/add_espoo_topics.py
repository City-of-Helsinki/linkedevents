# This file has been adapted from add_helsinki_topics.py
from functools import lru_cache

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Keyword, KeywordSet, DataSource

logger = logging.getLogger(__name__)

ESPOO_TOPIC_KEYWORD_SET_DATA = {
    'id': 'espoo:topics',
    'name_en': 'Espoo\'s topics',
    'name_fi': 'Espoon aihepiirit',
    'name_sv': 'Esbos ämnesområden',
    'data_source_id': 'espoo',
    'usage': KeywordSet.KEYWORD,
}

# All of the Espoo topic keywords are based on existing YSO keywords
TOPIC_KEYWORD_IDS = [
    'yso:p1797',  # asuminen
    'yso:p1235',  # elokuvat
    'yso:p1947',  # hyvinvointi
    'yso:p8270',  # kaupunkisuunnittelu
    'yso:p2787',  # kirjastot
    'yso:p8113',  # kirjallisuus
    'yso:p360',  # kulttuuritapahtumat
    'yso:p3466',  # liikenne
    'yso:p916',  # liikunta
    'yso:p3917',  # matkailu
    'yso:p4934',  # museot
    'yso:p1808',  # musiikki
    'yso:p5121',  # näyttelyt
    'yso:p2630',  # opetus
    'yso:p10727',  # osallistuminen
    'yso:p8743',  # päätöksenteko
    'yso:p3673',  # rakentaminen
    'yso:p1278',  # tanssi
    'yso:p2625',  # teatteritaide
    'yso:p2762',  # terveys
    'yso:p7349',  # turvallisuus
    'yso:p1810',  # työ
    'yso:p2771',  # ulkoilu
    'yso:p1650',  # varhaiskasvatus
    'yso:p6033',  # ympäristö
    'yso:p1182',  # yrittäjyys
]


class Command(BaseCommand):
    help = "Creates a keyword set with Espoo's topics."

    @lru_cache()
    def _get_keyword_obj(self, keyword_id):
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            raise CommandError(f"keyword \"{keyword_id}\" does not exist")
        return keyword

    @transaction.atomic()
    def _create_espoo_topics_keyword_set(self):
        logger.info('creating Espoo topics keyword set...')

        # create the set itself
        keyword_set, created = KeywordSet.objects.update_or_create(
            id=ESPOO_TOPIC_KEYWORD_SET_DATA['id'],
            defaults=ESPOO_TOPIC_KEYWORD_SET_DATA
        )
        if created:
            logger.info(f"created keyword set \"{ESPOO_TOPIC_KEYWORD_SET_DATA['id']}\"")
        else:
            logger.info(f"keyword set \"{ESPOO_TOPIC_KEYWORD_SET_DATA['id']}\" already exists")

        # add the keywords to the set
        existing_keywords = set(keyword_set.keywords.all())
        for keyword_id in TOPIC_KEYWORD_IDS:
            keyword = self._get_keyword_obj(keyword_id)

            if keyword not in existing_keywords:
                keyword_set.keywords.add(keyword)
                existing_keywords.add(keyword)
                logger.info(f"added {keyword.name} ({keyword_id}) to the keyword set")

    def handle(self, *args, **options):
        # Espoo data source must be created if missing. Note that it is not necessarily the system data source.
        # If we are creating it, it *may* still be the system data source, so it must be user editable!
        espoo_data_source_defaults = {'user_editable': True}
        DataSource.objects.get_or_create(id=ESPOO_TOPIC_KEYWORD_SET_DATA['data_source_id'],
                                         defaults=espoo_data_source_defaults)
        self._create_espoo_topics_keyword_set()
        logger.info('all done')
