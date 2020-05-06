from functools import lru_cache

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Event, Keyword, KeywordSet, DataSource

'''
HELSINKI_KEYWORD_SET_DATA = {
    'id': 'helsinki:audiences',
    'name_en': 'Helsinki audiences',
    'name_fi': 'Helsinki kohderyhmät',
    'name_sv': 'Helsingfors invånargrupper',
    'data_source_id': 'helsinki',
    'usage': KeywordSet.AUDIENCE,
}
'''
#Turku specific 
TURKU_KEYWORD_SET_DATA = {
    'id': 'turku:audiences',
    'name_en': 'Turku audiences',
    'name_fi': 'Turku kohderyhmät',
    'name_sv': 'Åbo invånargrupper',
    'data_source_id': 'turku',
    'usage': KeywordSet.AUDIENCE,
}

'''
# keyword id mapping from hel.fi to YSO
KEYWORD_MAPPING = {
    'helfi:1': ['yso:p4354', 'yso:p13050'],  # lapset ja lapsiperheet -> lapset (ikään liittyvä rooli) & lapsiperheet
    'helfi:2': ['yso:p11617'],  # nuoret -> nuoret (ikään liittyvä rooli)
    'helfi:3': ['yso:p6165'],  # maahanmuuttajat -> maahanmuuttajat
    'helfi:4': ['yso:p7179'],  # vammaiset -> vammaiset
    'helfi:5': ['yso:p2433'],  # vanhukset -> ikääntyneet
    'helfi:6': ['yso:p3128'],  # yritykset -> yritykset
    'helfi:7': ['yso:p1393'],  # yhdistykset -> järjestöt
}
'''
city = TURKU_KEYWORD_SET_DATA['data_source_id']

KEYWORD_MAPPING = {
    city+':1': ['yso:p27976'], #-> Aikuiset
    city+':2': ['yso:p13050'], #-> Lapsiperheet
    city+':3': ['yso:p6165'], #-> Maahanmuuttujat
    city+':4': ['yso:p16596'], #-> Matkailijat
    city+':5': ['yso:p11617'], #-> Nuoret
    city+':6': ['yso:p2433'], #-> Seniorit
    city+':7': ['yso:p9607'], #-> Työnhakijat
    city+':8': ['yso:p7179'], #-> Vammaiset
    city+':9': ['yso:p15937', 'yso:p27455'], #-> Vauvat ja Taaperot
    city+':10': ['yso:p6946'], #-> Viranomaiset
    city+':11': ['yso:p1393', 'yso:p3835'], #-> Yhdistykset ja Yhteisöt
    city+':12': ['yso:p1178'], #-> Yrittäjät
}

'''
YSO_SOTE_KEYWORD_IDS = [
    'yso:p12297',  # mielenterveyspotilaat
    'yso:p23886',  # päihdekeskuskuntoutujat
]
'''
YSO_SOTE_KEYWORD_IDS = []
'''
NEW_SOTE_KEYWORDS_DATA = [
    {
        'id': 'helsinki:aflfbatkwe',
        'name_fi': 'omaishoitoperheet',
        'data_source_id': 'helsinki',
    },
    {
        'id': 'helsinki:aflfbat76e',
        'name_fi': 'palvelukeskuskortti',
        'data_source_id': 'helsinki',
    }
]
'''
NEW_SOTE_KEYWORDS_DATA = []

class Command(BaseCommand):
    help = "Creates SOTE keywords and Turku audience keyword set and adds YSO audience keywords to events."

    @lru_cache()
    def get_keyword_obj(self, keyword_id):
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            raise CommandError('keyword "%s" does not exist' % keyword_id)
        return keyword

    @transaction.atomic()
    def create_sote_keywords(self):
        self.stdout.write('creating new SOTE keywords...')

        for new_keyword_data in NEW_SOTE_KEYWORDS_DATA:
            keyword_set, created = Keyword.objects.update_or_create(
                id=new_keyword_data['id'],
                defaults=new_keyword_data
            )
            if created:
                self.stdout.write('created keyword %s (%s)' % (new_keyword_data['name_fi'], new_keyword_data['id']))
            else:
                self.stdout.write('keyword %s (%s) already exist' % (new_keyword_data['name_fi'],
                                                                     new_keyword_data['id']))

    @transaction.atomic()
    def create_helsinki_audiences_keyword_set(self):
        self.stdout.write('creating Helsinki audiences keyword set...')

        # create the set itself
        keyword_set, created = KeywordSet.objects.update_or_create(
            id=HELSINKI_KEYWORD_SET_DATA['id'],
            defaults=HELSINKI_KEYWORD_SET_DATA
        )
        if created:
            self.stdout.write('created keyword set "%s"' % HELSINKI_KEYWORD_SET_DATA['id'])
        else:
            self.stdout.write('keyword set "%s" already exist' % HELSINKI_KEYWORD_SET_DATA['id'])

        # flatten YSO keyword IDs
        yso_keyword_ids = [val for sublist in KEYWORD_MAPPING.values() for val in sublist]

        # keywords to add to the set = YSO keywords corresponding to hel.fi + YSO SOTE keywords + new SOTE keywords
        keyword_ids = yso_keyword_ids + YSO_SOTE_KEYWORD_IDS + [kw['id'] for kw in NEW_SOTE_KEYWORDS_DATA]

        # add the keywords to the set
        existing_keywords = set(keyword_set.keywords.all())
        for keyword_id in keyword_ids:
            keyword = self.get_keyword_obj(keyword_id)

            if keyword not in existing_keywords:
                keyword_set.keywords.add(keyword)
                existing_keywords.add(keyword)
                self.stdout.write('added %s (%s) to the keyword set' % (keyword.name, keyword_id))

    @transaction.atomic()
    def add_yso_audience_keywords_to_events(self):
        self.stdout.write('adding YSO audience keywords to events...')

        for event in Event.objects.exclude(audience__isnull=True).prefetch_related('audience'):
            for audience in event.audience.all():

                # if current audience is a valid hel.fi audience keyword, iterate YSO keywords corresponding to it
                for yso_keyword_id in KEYWORD_MAPPING.get(audience.id, []):
                    yso_keyword_obj = self.get_keyword_obj(yso_keyword_id)

                    if yso_keyword_obj not in event.audience.all():
                        event.audience.add(yso_keyword_obj)
                        self.stdout.write('added %s (%s) to %s' % (yso_keyword_obj, yso_keyword_id, event))

    def handle(self, *args, **options):
        # Helsinki data source must be created if missing. Note that it is not necessarily the system data source.
        # If we are creating it, it *may* still be the system data source, so it must be user editable!
        turku_data_source_defaults = {'user_editable': True}
        #Turku specific datasource.
        
        DataSource.objects.get_or_create(id=TURKU_KEYWORD_SET_DATA['data_source_id'],
                                         defaults=turku_data_source_defaults)
        self.create_sote_keywords()
        self.create_helsinki_audiences_keyword_set()
        self.add_yso_audience_keywords_to_events()
        self.stdout.write('all done')
