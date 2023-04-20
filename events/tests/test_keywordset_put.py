import pytest
from rest_framework import status

from events.tests.test_keywordset_post import create_keyword_set
from events.tests.utils import versioned_reverse as reverse

# === util methods ===


def update_keyword_set(api_client, edit_url, keyword_set_data, data_source=None):
    if data_source:
        api_client.credentials(apikey=data_source.api_key)

    response = api_client.put(edit_url, keyword_set_data, format="json")
    return response


def assert_update_keyword_set(api_client, keyword_set, data_source=None):
    detail_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.pk})
    response = api_client.get(detail_url, format="json")
    assert response.status_code == status.HTTP_200_OK

    keyword_set_data = response.data
    keyword_set_data["keywords"] = []
    response = update_keyword_set(api_client, detail_url, keyword_set_data, data_source)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["keywords"] == []


# === tests ===


@pytest.mark.django_db
def test__update_keywordset(api_client, keyword_set_dict, user):
    api_client.force_authenticate(user)

    response = create_keyword_set(api_client, keyword_set_dict)

    keyword_set_data = response.data
    keyword_set_data["name"] = {"fi": "Avainsanaryhmä 2", "en": "Keyword set name"}
    kw_id = keyword_set_data.pop("@id")

    response = update_keyword_set(api_client, kw_id, keyword_set_data)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"]["fi"] == keyword_set_data["name"]["fi"]


@pytest.mark.django_db
def test__non_admin_cannot_update_keywordset(
    api_client, keyword_set, keyword_set_dict, user
):
    keyword_set.organization.admin_users.remove(user)
    api_client.force_authenticate(user)

    detail_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.pk})
    response = update_keyword_set(api_client, detail_url, keyword_set_dict)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__admin_can_update_keywordset_from_another_data_source(
    api_client, keyword_set2, other_data_source, organization, user
):
    other_data_source.owner = organization
    other_data_source.user_editable_resources = True
    other_data_source.save()
    keyword_set2.organization = organization
    keyword_set2.name = {
        "en": "Test keyword set - updated",
        "fi": "Testiavainsanaryhmä - updated",
    }
    keyword_set2.save()
    api_client.force_authenticate(user)

    assert_update_keyword_set(api_client, keyword_set2)


@pytest.mark.django_db
def test__keywordset_id_cannot_be_updated(api_client, keyword_set_dict, user):
    api_client.force_authenticate(user)

    response = create_keyword_set(api_client, keyword_set_dict)

    keyword_set_data = response.data
    keyword_set_data["id"] = "changed_id"
    kw_id = keyword_set_data.pop("@id")

    response = update_keyword_set(api_client, kw_id, keyword_set_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["id"] == "You may not change the id of an existing object."


@pytest.mark.django_db
def test__keywordset_organization_cannot_be_updated(
    api_client, keyword_set_dict, organization2, user
):
    api_client.force_authenticate(user)

    response = create_keyword_set(api_client, keyword_set_dict)

    keyword_set_data = response.data
    keyword_set_data["organization"] = organization2.id
    kw_id = keyword_set_data.pop("@id")

    response = update_keyword_set(api_client, kw_id, keyword_set_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["organization"]
        == "You may not change the organization of an existing object."
    )


@pytest.mark.django_db
def test__keywordset_data_source_cannot_be_updated(
    api_client, keyword_set_dict, other_data_source, user
):
    api_client.force_authenticate(user)

    response = create_keyword_set(api_client, keyword_set_dict)

    keyword_set_data = response.data
    keyword_set_data["data_source"] = other_data_source.id
    kw_id = keyword_set_data.pop("@id")

    response = update_keyword_set(api_client, kw_id, keyword_set_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["data_source"]
        == "You may not change the data source of an existing object."
    )


@pytest.mark.django_db
def test__correct_api_key_can_update_keywordset(
    api_client, keyword_set, data_source, organization
):
    data_source.owner = organization
    data_source.save()

    assert_update_keyword_set(api_client, keyword_set, data_source)


@pytest.mark.django_db
def test__api_key_from_wrong_data_source_cannot_update_keywordset(
    api_client, keyword_set, keyword_set_dict, other_data_source
):
    detail_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.pk})
    response = update_keyword_set(
        api_client, detail_url, keyword_set_dict, other_data_source
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_without_organization_cannot_update_keywordset(
    api_client, keyword_set, keyword_set_dict, data_source
):
    detail_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.pk})
    response = update_keyword_set(
        api_client,
        detail_url,
        keyword_set_dict,
        data_source,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_update_keywordset(api_client, keyword, keyword_dict):
    api_client.credentials(apikey="unknown")

    detail_url = reverse("keyword-detail", kwargs={"pk": keyword.pk})
    response = update_keyword_set(api_client, detail_url, keyword_dict)
    assert response.status_code == 401


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_update_keywordset(
    api_client, keyword_set, keyword_set_dict, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()
    api_client.force_authenticate(user)

    detail_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.pk})
    response = update_keyword_set(api_client, detail_url, keyword_set_dict)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_editable_resources_can_update_keywordset(
    api_client, keyword_set, keyword_set_dict, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user)

    keyword_set_data = keyword_set_dict
    keyword_set_data["id"] = keyword_set.id

    detail_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.pk})
    response = update_keyword_set(api_client, detail_url, keyword_set_dict)
    assert response.status_code == status.HTTP_200_OK
