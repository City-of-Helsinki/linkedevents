import pytest
from django.conf import settings

from events.models import Language

from .utils import assert_fields_exist, get
from .utils import versioned_reverse as reverse


@pytest.fixture
def default_languages():
    languages = []
    for language in settings.LANGUAGES:
        languages.append(
            Language.objects.get_or_create(id=language[0], name=language[1])[0]
        )
    return languages


# === util methods ===


def get_list(api_client):
    list_url = reverse("language-list")
    return get(api_client, list_url)


def get_detail(api_client, detail_pk):
    detail_url = reverse("language-detail", kwargs={"pk": detail_pk})
    return get(api_client, detail_url)


def assert_language_fields_exist(data):
    fields = ("id", "translation_available", "name", "@id", "@context", "@type")
    assert_fields_exist(data, fields)


# === tests ===


@pytest.mark.django_db
def test_get_language_list_check_fields_exist(api_client, default_languages):
    """
    Tests that language list endpoint returns the correct fields.
    """
    response = get_list(api_client)
    assert_language_fields_exist(response.data["data"][0])


@pytest.mark.django_db
def test_get_languaget_detail_check_fields_exist(api_client, default_languages):
    """
    Tests that language detail endpoint returns the correct fields.
    """
    response = get_detail(api_client, default_languages[0].pk)
    assert_language_fields_exist(response.data)


@pytest.mark.django_db
def test_get_language_check_translation_available(api_client, default_languages):
    """
    Tests that a default language's translation available is True while an additional language's is False.
    """
    Language.objects.get_or_create(id="tlh", name="Klingon")

    response = get_detail(api_client, "fi")
    assert response.data["translation_available"] is True

    response = get_detail(api_client, "tlh")
    assert response.data["translation_available"] is False
