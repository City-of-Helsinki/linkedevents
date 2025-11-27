import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from events.models import Keyword, KeywordSet

logger = logging.getLogger(__name__)

ORGANIZATION_ID = "ahjo:u42030030"


KEYWORD_SET = [
    {
        "id": "helsinki:education_levels",
        "usage": KeywordSet.KEYWORD,
        "data_source_id": "helsinki",
        "organization_id": ORGANIZATION_ID,
        "name": {
            "fi": "Helsinki Opintojen tasot",
            "sv": "Helsinki Utbildningens nivåer",
            "en": "Helsinki Education levels",
        },
        "keywords": [
            "helsinki:adult_education",
            "helsinki:vocational_school",
            "helsinki:institution_of_higher_education",
            "helsinki:general_upper_secondary_school",
        ],
    },
    {
        "id": "helsinki:education_models",
        "usage": KeywordSet.KEYWORD,
        "data_source_id": "helsinki",
        "organization_id": ORGANIZATION_ID,
        "name": {
            "fi": "Helsinki Opiskelumuodot",
            "sv": "Helsinki Utbildningsformer",
            "en": "Helsinki Education models",
        },
        "keywords": [
            "helsinki:online_learning",
            "helsinki:hybrid_learning",
            "helsinki:contact_learning",
            "helsinki:remote_learning",
        ],
    },
]

KEYWORDS = {
    "helsinki:online_learning": {
        "aggregate": False,
        "deprecated": False,
        "has_upcoming_events": False,
        "data_source_id": "helsinki",
        "publisher_id": ORGANIZATION_ID,
        "name": {"fi": "verkko-opiskelu", "sv": "nätstudier", "en": "online learning"},
    },
    "helsinki:hybrid_learning": {
        "aggregate": False,
        "deprecated": False,
        "has_upcoming_events": False,
        "data_source_id": "helsinki",
        "publisher_id": ORGANIZATION_ID,
        "replaced_by": None,
        "name": {
            "fi": "hybridiopiskelu",
            "sv": "hybrid studier",
            "en": "hybrid learning",
        },
    },
    "helsinki:contact_learning": {
        "aggregate": False,
        "deprecated": False,
        "has_upcoming_events": False,
        "data_source_id": "helsinki",
        "publisher_id": ORGANIZATION_ID,
        "name": {
            "fi": "lähiopiskelu",
            "sv": "kontaktstudier",
            "en": "contact learning",
        },
    },
    "helsinki:remote_learning": {
        "aggregate": False,
        "deprecated": False,
        "has_upcoming_events": True,
        "data_source_id": "helsinki",
        "publisher_id": ORGANIZATION_ID,
        "name": {
            "fi": "etäopiskelu",
            "sv": "distansundervisning",
            "en": "remote learning",
        },
    },
    "helsinki:adult_education": {
        "aggregate": False,
        "deprecated": False,
        "has_upcoming_events": False,
        "data_source_id": "helsinki",
        "publisher_id": ORGANIZATION_ID,
        "name": {
            "fi": "työväenopisto",
            "sv": "arbetarinstitutet",
            "en": "adult education",
        },
    },
    "helsinki:vocational_school": {
        "aggregate": False,
        "deprecated": False,
        "has_upcoming_events": True,
        "data_source_id": "helsinki",
        "publisher_id": ORGANIZATION_ID,
        "name": {"fi": "ammattiopisto", "sv": "yrkesskola", "en": "vocational school"},
    },
    "helsinki:institution_of_higher_education": {
        "aggregate": False,
        "deprecated": False,
        "has_upcoming_events": False,
        "data_source_id": "helsinki",
        "publisher_id": ORGANIZATION_ID,
        "name": {
            "fi": "korkeakoulu",
            "sv": "högskola",
            "en": "institution of higher education",
        },
    },
    "helsinki:general_upper_secondary_school": {
        "aggregate": False,
        "deprecated": False,
        "has_upcoming_events": False,
        "data_source_id": "helsinki",
        "publisher_id": ORGANIZATION_ID,
        "name": {
            "fi": "lukio",
            "sv": "gymnasiet",
            "en": "general upper secondary school",
        },
    },
    "helsinki:secondary_schools_cross_institutional_studies": {
        "aggregate": False,
        "deprecated": False,
        "has_upcoming_events": False,
        "data_source_id": "helsinki",
        "publisher_id": ORGANIZATION_ID,
        "name": {
            "fi": "toisen asteen ristiinopiskelu",
            "sv": "andra stadiets korsstudier",
            "en": "secondary schools cross-institutional studies",
        },
    },
}


class Command(BaseCommand):
    help = "Adds kasko keywords."

    @transaction.atomic
    def handle(self, *args, **options):
        self.create_keywords()
        self.create_keyword_set()

    def create_keywords(self):
        for kw_id, kw_data in KEYWORDS.items():
            kw_data = kw_data.copy()
            kw_data["id"] = kw_id
            self._create_kw_object(Keyword, kw_data)

    def create_keyword_set(self):
        for kw_set_data in KEYWORD_SET:
            kw_set_data = kw_set_data.copy()
            self._create_keyword_set_with_keywords(kw_set_data)

    def _create_keyword_set_with_keywords(self, kw_set_data) -> KeywordSet:
        keyword_ids = kw_set_data.pop("keywords")
        kw_set = self._create_kw_object(KeywordSet, kw_set_data)

        for kw_id in keyword_ids:
            kw_set.keywords.add(Keyword.objects.get(id=kw_id))

    def _create_kw_object(
        self, kw_class: type[Keyword] | type[KeywordSet], object_data: dict
    ) -> KeywordSet | Keyword:
        object_data = object_data.copy()
        names = {f"name_{lang}": value for lang, value in object_data["name"].items()}
        object_data.pop("name")
        object_id = object_data.pop("id")

        obj, _ = kw_class.objects.get_or_create(
            id=object_id, defaults={**object_data, **names}
        )

        return obj
