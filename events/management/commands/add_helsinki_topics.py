from functools import lru_cache

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import DataSource, Keyword, KeywordSet

HELSINKI_KEYWORD_SET_DATA = {
    "id": "helsinki:topics",
    "name_en": "Helsinki topics",
    "name_fi": "Helsinki-aihepiirit",
    "name_sv": "Helsingfors-teman",
    "data_source_id": "helsinki",
    "usage": KeywordSet.KEYWORD,
}

HELSINKI_KEYWORD_IDS = [
    "yso:p1235",  # elokuvat
    "yso:p1947",  # hyvinvointi
    "yso:p14004",  # keskustelu
    "yso:p11185",  # konsertit
    "yso:p360",  # kulttuuritapahtumat
    "yso:p2739",  # kuvataide
    "yso:p316",  # leikkiminen
    "yso:p916",  # liikunta
    "yso:p15875",  # luennot
    "yso:p1808",  # musiikki
    "yso:p5121",  # näyttelyt
    "yso:p2149",  # opastus
    "yso:p10727",  # osallistuminen
    "yso:p6062",  # pelit
    "yso:p3670",  # ruoka
    "yso:p1278",  # tanssi
    "yso:p2625",  # teatteritaide
    "yso:p19245",  # työpajat
    "yso:p2771",  # ulkoilu
    "yso:p965",  # urheilu
]


class Command(BaseCommand):
    help = "Creates Helsinki topics keyword set."

    @lru_cache()  # noqa: B019
    def get_keyword_obj(self, keyword_id):
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            raise CommandError('keyword "%s" does not exist' % keyword_id)
        return keyword

    @transaction.atomic
    def create_helsinki_topics_keyword_set(self):
        self.stdout.write("creating Helsinki topics keyword set...")

        # create the set itself
        keyword_set, created = KeywordSet.objects.update_or_create(
            id=HELSINKI_KEYWORD_SET_DATA["id"], defaults=HELSINKI_KEYWORD_SET_DATA
        )
        if created:
            self.stdout.write(
                'created keyword set "%s"' % HELSINKI_KEYWORD_SET_DATA["id"]
            )
        else:
            self.stdout.write(
                'keyword set "%s" already exist' % HELSINKI_KEYWORD_SET_DATA["id"]
            )

        # add the keywords to the set
        existing_keywords = set(keyword_set.keywords.all())
        for keyword_id in HELSINKI_KEYWORD_IDS:
            keyword = self.get_keyword_obj(keyword_id)

            if keyword not in existing_keywords:
                keyword_set.keywords.add(keyword)
                existing_keywords.add(keyword)
                self.stdout.write(
                    "added %s (%s) to the keyword set" % (keyword.name, keyword_id)
                )

    def handle(self, *args, **options):
        # Helsinki data source must be created if missing. Note that it is not necessarily the system data source.  # noqa: E501
        # If we are creating it, it *may* still be the system data source, so it
        # must be user editable!
        helsinki_data_source_defaults = {
            "user_editable_resources": True,
            "user_editable_organizations": True,
        }
        DataSource.objects.get_or_create(
            id=HELSINKI_KEYWORD_SET_DATA["data_source_id"],
            defaults=helsinki_data_source_defaults,
        )
        self.create_helsinki_topics_keyword_set()
        self.stdout.write("all done")
