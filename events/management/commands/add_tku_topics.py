from functools import lru_cache

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import Keyword, KeywordSet, DataSource

TURKU_KEYWORD_SET_DATA = {
    'id': 'turku:topic',
    'name_en': 'Turku topic',
    'name_fi': 'Turku-aihepiiri',
    'name_sv': 'Åbo-tema',
    'data_source_id': 'turku',
    'usage': KeywordSet.KEYWORD,
}

TURKU_KEYWORD_IDS = [
    # Event content based:
    'tsl:p28',  # Kuvataide
    'tsl:p29',  # Tanssi
    'tsl:p9',  # Musiikki
    'tsl:p11',  # Teatteri, performanssi ja sirkus
    'tsl:p4',  # Kirjallisuus ja sanataide
    'tsl:p30',  # Elokuva
    'tsl:p31',  # Käsityöt
    'tsl:p10',  # Ruoka ja juoma
    'tsl:p7',  # Liikunta ja urheilu
    'tsl:p32',  # Terveys ja hyvinvointi
    'tsl:p33',  # Luonto ja kulttuuriympäristö
    'tsl:p34',  # Uskonto ja hengellisyys
    'tsl:p35',  # Yritystoiminta ja työelämä
    'tsl:p36',  # Yhteiskunta
    'tsl:p37',  # Historia
    'tsl:p14',  # Muut

    # Event type based:
    'tsl:p38',  # Festivaalit
    'tsl:p39',  # Kaupunkitapahtumat
    'tsl:p40',  # Keskustelutilaisuudet
    'tsl:p41',  # Kilpailut
    'tsl:p42',  # Kokoukset, seminaarit ja kongressit
    'tsl:p43',  # Konsertit
    'tsl:p44',  # Koulutustapahtumat
    'tsl:p45',  # Leirit
    'tsl:p46',  # Luennot
    'tsl:p47',  # Markkinat
    'tsl:p48',  # Messut
    'tsl:p49',  # Myyjäiset
    'tsl:p50',  # Näyttelyt
    'tsl:p51',  # Opastukset
    'tsl:p52',  # Retket
    'tsl:p53',  # Työpajat
    'tsl:p54',  # Verkostoitumistapahtumat
    'tsl:p55',  # Muu
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
