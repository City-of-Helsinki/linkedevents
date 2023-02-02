import pytest
from rest_framework.exceptions import ValidationError

from events.api import KeywordSerializer
from events.tests.utils import versioned_reverse as reverse


@pytest.mark.django_db
def test_keywordset_cannot_have_deprecated_keyword(keyword, keyword_set):
    keyword.deprecated = True
    keyword.save()
    with pytest.raises(ValidationError):
        keyword_set.save()


@pytest.mark.django_db
def test_create_id_second_part_specified(user, api_client, keyword, keyword2):
    url = reverse("keywordset-list")
    api_client.force_authenticate(user)

    keyword_set_load = {
        "id_second_part": "loppuosa",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä", "en": "KeywordSet name"},
        "keywords": [
            {"@id": reverse(KeywordSerializer().view_name, kwargs={"pk": keyword.id})},
            {"@id": reverse(KeywordSerializer().view_name, kwargs={"pk": keyword2.id})},
        ],
    }

    response = api_client.post(url, keyword_set_load, format="json")
    assert response.status_code == 201
    response = api_client.get(f"{url}system:loppuosa/")
    assert keyword_set_load["name"] == response.data["name"]
    keywords = set(
        [i["@id"].rstrip("/").split("/")[-1] for i in response.data["keywords"]]
    )
    assert keywords == set([keyword.id, keyword2.id])


@pytest.mark.django_db
def test_create_no_keywords(user, api_client, keyword, keyword2):
    url = reverse("keywordset-list")
    api_client.force_authenticate(user)
    keyword_set_load = {
        "id_second_part": "loppuosa2",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä", "en": "KeywordSet name"},
    }

    response = api_client.post(url, keyword_set_load, format="json")
    assert response.status_code == 201


@pytest.mark.django_db
def test_create_id_specified(user, api_client, keyword, keyword2):
    url = reverse("keywordset-list")
    api_client.force_authenticate(user)
    keyword_set_load = {
        "id": "system:loppuosa3",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä", "en": "KeywordSet name"},
    }

    response = api_client.post(url, keyword_set_load, format="json")
    assert response.status_code == 201


@pytest.mark.django_db
def test_repeating_id_blocked(user, api_client, keyword_set, keyword, keyword2):
    url = reverse("keywordset-list")
    api_client.force_authenticate(user)

    keyword_set_load = {
        "id": "system:loppuosa3",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä", "en": "KeywordSet name"},
    }

    keyword_set_load = {
        "id": "system:loppuosa3",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä", "en": "KeywordSet name"},
    }

    api_client.post(url, keyword_set_load, format="json")
    response = api_client.post(url, keyword_set_load, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_non_matching_datasource(user, api_client, keyword_set, keyword, keyword2):
    url = reverse("keywordset-list")
    keyword_set_load = {
        "id": "wrongdatasource:loppuosa3",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä", "en": "KeywordSet name"},
    }

    response = api_client.post(url, keyword_set_load, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_create_fails_for_anonymous(user, api_client):
    url = reverse("keywordset-list")
    api_client.force_authenticate(None)

    keyword_set_load = {
        "id_second_part": "loppuosa",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä", "en": "KeywordSet name"},
    }

    response = api_client.post(url, keyword_set_load, format="json")
    assert response.data["detail"].code == "not_authenticated"


@pytest.mark.django_db
def test_put(user, user2, api_client, keyword, keyword2):
    url = reverse("keywordset-list")
    api_client.force_authenticate(user)

    keyword_set_load = {
        "id": "system:id",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä", "en": "KeywordSet name"},
        "keywords": [
            {"@id": reverse(KeywordSerializer().view_name, kwargs={"pk": keyword.id})},
            {"@id": reverse(KeywordSerializer().view_name, kwargs={"pk": keyword2.id})},
        ],
    }

    response = api_client.post(url, keyword_set_load, format="json")
    assert response.status_code == 201

    keyword_set_load = {
        "id": "system:id",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä2", "en": "KeywordSet name"},
    }

    api_client.force_authenticate(user)
    response = api_client.put(f"{url}system:id/", keyword_set_load, format="json")
    assert response.status_code == 200
    response = api_client.get(f"{url}system:id/")
    assert response.data["name"]["fi"] == keyword_set_load["name"]["fi"]


@pytest.mark.django_db
def test_put_user_from_empty_or_another_org(
    user, user2, organization2, api_client, keyword, keyword2
):
    url = reverse("keywordset-list")
    api_client.force_authenticate(user)

    keyword_set_load = {
        "id": "system:id",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä", "en": "KeywordSet name"},
        "keywords": [
            {"@id": reverse(KeywordSerializer().view_name, kwargs={"pk": keyword.id})},
            {"@id": reverse(KeywordSerializer().view_name, kwargs={"pk": keyword2.id})},
        ],
    }

    response = api_client.post(url, keyword_set_load, format="json")
    assert response.status_code == 201

    keyword_set_load = {
        "id": "system:id",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä2", "en": "KeywordSet name"},
    }

    api_client.force_authenticate(user2)
    response = api_client.put(f"{url}system:id/", keyword_set_load, format="json")
    assert response.status_code == 403

    api_client.force_authenticate(user)
    response = api_client.put(f"{url}system:id/", keyword_set_load, format="json")
    assert response.status_code == 200


@pytest.mark.django_db
def test_delete(user, user2, organization2, api_client, keyword, keyword2):
    url = reverse("keywordset-list")
    api_client.force_authenticate(user)

    keyword_set_load = {
        "id": "system:id",
        "usage": "audience",
        "name": {"fi": "AvainSanaRyhmä", "en": "KeywordSet name"},
        "keywords": [
            {"@id": reverse(KeywordSerializer().view_name, kwargs={"pk": keyword.id})},
            {"@id": reverse(KeywordSerializer().view_name, kwargs={"pk": keyword2.id})},
        ],
    }

    response = api_client.post(url, keyword_set_load, format="json")
    assert response.status_code == 201

    api_client.force_authenticate(user2)
    response = api_client.delete(f"{url}system:id/", format="json")
    assert response.status_code == 403

    api_client.force_authenticate(user)
    response = api_client.delete(f"{url}system:id/")
    assert response.status_code == 204

    response = api_client.delete(f"{url}system:id/")
    assert response.status_code == 403

    response = api_client.get(f"{url}system:id/")
    assert response.status_code == 404
