import pytest
from django.core.management import call_command

from events.management.commands.add_kasko_keywords import KEYWORD_SET, KEYWORDS
from events.models import Keyword, KeywordSet
from events.tests.factories import DataSourceFactory, OrganizationFactory


@pytest.mark.django_db
def test_kasko_keyword_set():
    DataSourceFactory(id="helsinki")
    OrganizationFactory(id="ahjo:u42030030")

    call_command("add_kasko_keywords")

    for kw_set_data in KEYWORD_SET:
        kw_set = KeywordSet.objects.get(id=kw_set_data["id"])
        assert kw_set.keywords.count() == len(kw_set_data["keywords"])

        for field, value in kw_set_data.items():
            if field == "keywords":
                continue
            if field == "name":
                for lang, name in value.items():
                    assert getattr(kw_set, f"name_{lang}") == name
                continue
            assert getattr(kw_set, field) == value

        assert kw_set.keywords.filter(id__in=kw_set_data["keywords"]).count() == len(
            kw_set_data["keywords"]
        )


@pytest.mark.django_db
def test_kasko_keywords():
    DataSourceFactory(id="helsinki")
    org = OrganizationFactory(id="ahjo:u42030030")
    call_command("add_kasko_keywords")

    for kw_id, kw_data in KEYWORDS.items():
        kw = Keyword.objects.get(id=kw_id)
        for field, value in kw_data.items():
            if field == "name":
                for lang, name in value.items():
                    assert getattr(kw, f"name_{lang}") == name
                continue
            assert getattr(kw, field) == value

    assert Keyword.objects.filter(publisher=org).count() == len(KEYWORDS)
