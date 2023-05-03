from functools import lru_cache

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.models import DataSource, Keyword, KeywordSet

HELFI_KEYWORD_SET_DATA = {
    "id": "helfi:topics",
    "name_en": "www.hel.fi themes",
    "name_fi": "www.hel.fi-aihepiirit",
    "name_sv": "www.hel.fi-teman",
    "data_source_id": "helfi",
    "usage": KeywordSet.KEYWORD,
}

NEW_HELFI_KEYWORDS_DATA = [
    {
        "id": "helfi:8",
        "name_fi": "Kaupunki ja hallinto",
        "name_sv": "Staden och förvaltning",
        "name_en": "City administration",
        "data_source_id": "helfi",
    },
    {
        "id": "helfi:9",
        "name_fi": "Sosiaali- ja terveyspalvelut",
        "name_sv": "Social- och hälsovård",
        "name_en": "Social services and health care",
        "data_source_id": "helfi",
    },
    {
        "id": "helfi:10",
        "name_fi": "Liikenne ja kartat",
        "name_sv": "Kartor och trafik",
        "name_en": "Maps and transport",
        "data_source_id": "helfi",
    },
    {
        "id": "helfi:11",
        "name_fi": "Päivähoito ja koulutus",
        "name_sv": "Dagvård och utbildning",
        "name_en": "Daycare and education",
        "data_source_id": "helfi",
    },
    {
        "id": "helfi:12",
        "name_fi": "Kulttuuri ja vapaa-aika",
        "name_sv": "Kultur och fritid",
        "name_en": "Culture and leisure",
        "data_source_id": "helfi",
    },
    {
        "id": "helfi:13",
        "name_fi": "Asuminen ja ympäristö",
        "name_sv": "Boende och miljö",
        "name_en": "Housing and environment",
        "data_source_id": "helfi",
    },
]


class Command(BaseCommand):
    help = "Creates www.hel.fi topic keywords and keyword set used by the UI."

    @lru_cache()  # noqa: B019
    def get_keyword_obj(self, keyword_id):
        try:
            keyword = Keyword.objects.get(id=keyword_id)
        except Keyword.DoesNotExist:
            raise CommandError('keyword "%s" does not exist' % keyword_id)
        return keyword

    @transaction.atomic
    def create_helfi_keywords(self):
        self.stdout.write("creating new helfi keywords...")

        for new_keyword_data in NEW_HELFI_KEYWORDS_DATA:
            keyword, created = Keyword.objects.update_or_create(
                id=new_keyword_data["id"], defaults=new_keyword_data
            )
            if created:
                self.stdout.write(
                    "created keyword %s (%s)"
                    % (new_keyword_data["name_fi"], new_keyword_data["id"])
                )
            else:
                self.stdout.write(
                    "keyword %s (%s) already exists"
                    % (new_keyword_data["name_fi"], new_keyword_data["id"])
                )

    @transaction.atomic
    def create_helfi_topics_keyword_set(self):
        self.stdout.write("creating www.hel.fi topics keyword set...")

        # create the set itself
        keyword_set, created = KeywordSet.objects.update_or_create(
            id=HELFI_KEYWORD_SET_DATA["id"], defaults=HELFI_KEYWORD_SET_DATA
        )
        if created:
            self.stdout.write('created keyword set "%s"' % HELFI_KEYWORD_SET_DATA["id"])
        else:
            self.stdout.write(
                'keyword set "%s" already exist' % HELFI_KEYWORD_SET_DATA["id"]
            )

        keyword_ids = [kw["id"] for kw in NEW_HELFI_KEYWORDS_DATA]

        # add the keywords to the set
        existing_keywords = set(keyword_set.keywords.all())
        for keyword_id in keyword_ids:
            keyword = self.get_keyword_obj(keyword_id)

            if keyword not in existing_keywords:
                keyword_set.keywords.add(keyword)
                existing_keywords.add(keyword)
                self.stdout.write(
                    "added %s (%s) to the keyword set" % (keyword.name, keyword_id)
                )

    def handle(self, *args, **options):
        # Helfi data source must be created if missing.
        DataSource.objects.get_or_create(id=HELFI_KEYWORD_SET_DATA["data_source_id"])
        self.create_helfi_keywords()
        self.create_helfi_topics_keyword_set()
        self.stdout.write("all done")
