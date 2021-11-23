from functools import lru_cache

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Keyword, KeywordSet, DataSource

TURKU_KEYWORD_SET_DATA = {
    'id': 'turku:audience',
    'name_en': 'Turku audience',
    'name_fi': 'Turku kohderyhmä',
    'name_sv': 'Åbo invånargrupp',
    'data_source_id': 'turku',
    'usage': KeywordSet.AUDIENCE,
}

TURKU_KEYWORD_IDS = [
    'tsl:p17',  # Vauvat ja taaperot
    'tsl:p18',  # Lapset ja lapsiperheet
    'tsl:p19',  # Nuoret
    'tsl:p20',  # Nuoret aikuiset
    'tsl:p21',  # Aikuiset
    'tsl:p22',  # Ikääntyneet
    'tsl:p23',  # Opiskelijat
    'tsl:p15',  # Maahanmuuttaneet
    'tsl:p16',  # Toimintarajoitteiset
    'tsl:p25',  # Työnhakijat
    'tsl:p26',  # Yrittäjät (Järjestöt, Viranomaiset)
]


class Command(BaseCommand):
    help = "Creates Turku audience keyword set."

    @ lru_cache()
    def get_keyword_obj(self, keyword_id):
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            raise CommandError('keyword "%s" does not exist' % keyword_id)
        return keyword

    @ transaction.atomic()
    def create_tsl_audience_keyword_set(self):
        self.stdout.write('creating Turku TSL audience keyword set...')

        # create the set itself
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

        # add the keywords to the set
        existing_keywords = set(keyword_set.keywords.all())
        for keyword_id in TURKU_KEYWORD_IDS:
            keyword = self.get_keyword_obj(keyword_id)

            if keyword not in existing_keywords:
                keyword_set.keywords.add(keyword)
                existing_keywords.add(keyword)
                self.stdout.write('added %s (%s) to the keyword set' %
                                  (keyword.name, keyword_id))

    def handle(self, *args, **options):
        # turku data source must be created if missing. Note that it is not necessarily the system data source.
        # If we are creating it, it *may* still be the system data source, so it must be user editable!
        turku_data_source_defaults = {
            'name': 'Kuntakohtainen data Turun Kaupunki', 'user_editable': True}
        DataSource.objects.get_or_create(id=TURKU_KEYWORD_SET_DATA['data_source_id'],
                                         defaults=turku_data_source_defaults)
        self.create_tsl_audience_keyword_set()
        self.stdout.write('all done')
