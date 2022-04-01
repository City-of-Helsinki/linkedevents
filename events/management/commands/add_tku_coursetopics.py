from functools import lru_cache

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Keyword, KeywordSet, DataSource

TURKU_KEYWORD_SET_DATA = {
    'id': 'turku:coursetopics',
    'name_en': 'Turku coursetopics',
    'name_fi': 'Turku-koulutusaihepiirit',
    'name_sv': 'Åbo-undervisningsämnen',
    'data_source_id': 'turku',
    'usage': KeywordSet.KEYWORD,
}

TURKU_KEYWORD_IDS = [
    # Event type based:
    'tsl:p59',  # Kädentaidot
    'tsl:p28',  # Kuvataide
    'tsl:p9',   # Musiikki
    'tsl:p56',  # Teatteri, tanssi ja sirkus
    'tsl:p60',  # Liikunta
    'tsl:p32',  # Terveys ja hyvinvointi
    'tsl:p61',  # Kielet ja kirjallisuus
    'tsl:p62',  # Viestintä ja media
    'tsl:p63',  # Historia, yhteiskunta ja talous
    'tsl:p64',  # Psykologia ja filosofia
    'tsl:p10',  # Ruoka ja juoma
    'tsl:p65',  # Kasvien hoito ja viljely
    'tsl:p66',  # Luonto ja ympäristö
    'tsl:p67',  # Tietotekniikka
    'tsl:p68',  # Muu koulutus
]


class Command(BaseCommand):
    help = "Creates Turku topics keyword set."

    @lru_cache()
    def get_keyword_obj(self, keyword_id):
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            raise CommandError('keyword "%s" does not exist' % keyword_id)
        return keyword

    @transaction.atomic()
    def create_tsl_topics_keyword_set(self):
        self.stdout.write('creating Turku TSL topics keyword set...')

        keyword_set, created = KeywordSet.objects.update_or_create(
            id=TURKU_KEYWORD_SET_DATA['id'],
            defaults=TURKU_KEYWORD_SET_DATA
        )
        if created:
            self.stdout.write('created keyword set "%s"' %
                              TURKU_KEYWORD_SET_DATA['id'])
        else:
            self.stdout.write('keyword set "%s" already exist' %
                              TURKU_KEYWORD_SET_DATA['id'])

        existing_keywords = set(keyword_set.keywords.all())
        for keyword_id in TURKU_KEYWORD_IDS:
            keyword = self.get_keyword_obj(keyword_id)

            if keyword not in existing_keywords:
                keyword_set.keywords.add(keyword)
                existing_keywords.add(keyword)
                self.stdout.write('added %s (%s) to the keyword set' %
                                  (keyword.name, keyword_id))

    def handle(self, *args, **options):
        turku_data_source_defaults = {
            'name': 'Kuntakohtainen data Turun Kaupunki', 'user_editable': True}
        DataSource.objects.get_or_create(id=TURKU_KEYWORD_SET_DATA['data_source_id'],
                                         defaults=turku_data_source_defaults)
        self.create_tsl_topics_keyword_set()
        self.stdout.write('all done')
