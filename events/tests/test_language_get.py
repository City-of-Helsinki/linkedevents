from collections import Counter

import pytest
from django.conf import settings
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Language

from .factories import LanguageFactory
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


def get_list(api_client, query_string=None):
    url = reverse("language-list")

    if query_string:
        url = f"{url}?{query_string}"

    return get(api_client, url)


def get_detail(api_client, detail_pk):
    detail_url = reverse("language-detail", kwargs={"pk": detail_pk})
    return get(api_client, detail_url)


def assert_language_fields_exist(data):
    fields = (
        "id",
        "translation_available",
        "name",
        "service_language",
        "@id",
        "@context",
        "@type",
    )
    assert_fields_exist(data, fields)


def assert_languages_in_response(languages, response):
    response_ids = {language["id"] for language in response.data["data"]}
    expected_ids = {language.id for language in languages}

    assert response_ids == expected_ids


# === tests ===


@pytest.mark.django_db
def test_get_language_list_check_fields_exist(api_client, default_languages):
    """
    Tests that language list endpoint returns the correct fields.
    """
    response = get_list(api_client)
    assert_language_fields_exist(response.data["data"][0])
    assert_languages_in_response(default_languages, response)


@pytest.mark.django_db
def test_get_list_filtered_by_service_language(api_client, languages):
    """
    Tests that language list is filtered by service language.
    """
    languages[0].service_language = True
    languages[0].save()
    languages[1].service_language = False
    languages[1].save()
    languages[2].service_language = False
    languages[2].save()

    response = get_list(api_client, "service_language=true")
    assert_languages_in_response([languages[0]], response)

    response = get_list(api_client, "service_language=false")
    assert_languages_in_response([languages[1], languages[2]], response)

    response = get_list(api_client)
    assert_languages_in_response(languages, response)


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


@pytest.mark.django_db
def test_language_id_is_audit_logged_on_get_detail(api_client, user):
    language = LanguageFactory(pk="fi")
    api_client.force_authenticate(user)

    response = get_detail(api_client, language.pk)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        language.pk
    ]


@pytest.mark.django_db
def test_language_id_is_audit_logged_on_get_list(api_client, user):
    language = LanguageFactory(pk="fi")
    language2 = LanguageFactory(pk="en")
    api_client.force_authenticate(user)
    response = get_list(api_client)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter([language.pk, language2.pk])
