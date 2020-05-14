from functools import lru_cache

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Keyword, KeywordSet, DataSource

TURKU_KEYWORD_SET_DATA = {
    'id': 'turku:topics',
    'name_en': 'Turku topics',
    'name_fi': 'Turku-aihepiirit',
    'name_sv': 'Åbo-teman',
    'data_source_id': 'turku',
    'usage': KeywordSet.KEYWORD,
}


TURKU_KEYWORD_IDS = [
    'yso:p1304',  # festivaalit 
    'yso:p38203',  # konferenssit (ja kokoukset)
    'yso:p4892', # messut
    'yso:p9376',  # myyjäiset
    'yso:p1808',  # musiikki
    'yso:p4934',  # museot
    'yso:p5121',  # näyttelyt
    'yso:p15875', # luennot
    'yso:p5164',  # osallisuus 
    'yso:p10647',  # monikulttuurisuus
    'yso:p25261', # retket
    'yso:p1917', # risteilyt
    'yso:p366',  # matkat
    'yso:p3917', # matkailu
    'yso:p2149',  # opastus
    'yso:p2625', # teatteritaide
    'yso:p2850', # muu esittävä taide
    'yso:p965', # urheilu
    'yso:p8113', # kirjallisuus
    'yso:p15238', # tapahtumat ja toiminnat
    'yso:p3670',  # ruoka
    'yso:p1278',  # tanssi
    'yso:p19245',  # työpajat
    'yso:p2771',  # ulkoilu
]


'''
HELSINKI_KEYWORD_IDS = [
    'yso:p1235',  # elokuvat
    'yso:p1947',  # hyvinvointi
    'yso:p14004',  # keskustelu
    'yso:p11185',  # konsertit
    'yso:p360',  # kulttuuritapahtumat
    'yso:p2739',  # kuvataide
    'yso:p316',  # leikkiminen
    'yso:p916',  # liikunta
    'yso:p15875',  # luennot
    'yso:p1808',  # musiikki
    'yso:p5121',  # näyttelyt
    'yso:p2149',  # opastus
    'yso:p10727',  # osallistuminen
    'yso:p6062',  # pelit
    'yso:p3670',  # ruoka
    'yso:p1278',  # tanssi
    'yso:p2625',  # teatteritaide
    'yso:p19245',  # työpajat
    'yso:p2771',  # ulkoilu
    'yso:p965'  # urheilu
]
'''

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
    def create_turku_topics_keyword_set(self):
        self.stdout.write('creating Turku topics keyword set...')

        # create the set itself
        keyword_set, created = KeywordSet.objects.update_or_create(
            id=TURKU_KEYWORD_SET_DATA['id'],
            defaults=TURKU_KEYWORD_SET_DATA
        )
        if created:
            self.stdout.write('created keyword set "%s"' % TURKU_KEYWORD_SET_DATA['id'])
        else:
            self.stdout.write('keyword set "%s" already exist' % TURKU_KEYWORD_SET_DATA['id'])

        # add the keywords to the set
        existing_keywords = set(keyword_set.keywords.all())
        for keyword_id in TURKU_KEYWORD_IDS:
            keyword = self.get_keyword_obj(keyword_id)

            if keyword not in existing_keywords:
                keyword_set.keywords.add(keyword)
                existing_keywords.add(keyword)
                self.stdout.write('added %s (%s) to the keyword set' % (keyword.name, keyword_id))

    def handle(self, *args, **options):
        # turku data source must be created if missing. Note that it is not necessarily the system data source.
        # If we are creating it, it *may* still be the system data source, so it must be user editable!
        turku_data_source_defaults = {'name':'Kuntakohtainen data Turun Kaupunki', 'user_editable': True}
        DataSource.objects.get_or_create(id=TURKU_KEYWORD_SET_DATA['data_source_id'],
                                         defaults=turku_data_source_defaults)
        self.create_turku_topics_keyword_set()
        self.stdout.write('all done')
