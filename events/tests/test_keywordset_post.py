import pytest
from rest_framework import status
from rest_framework.exceptions import ValidationError

from audit_log.models import AuditLogEntry
from events.tests.utils import assert_keyword_set_data_is_equal
from events.tests.utils import versioned_reverse as reverse


def create_keyword_set(api_client, keyword_set_data, data_source=None):
    if data_source:
        api_client.credentials(apikey=data_source.api_key)

    create_url = reverse("keywordset-list")
    response = api_client.post(create_url, keyword_set_data, format="json")
    return response


def assert_create_keyword_set(api_client, keyword_set_data, data_source=None):
    response = create_keyword_set(api_client, keyword_set_data, data_source)
    assert response.status_code == status.HTTP_201_CREATED
    assert_keyword_set_data_is_equal(keyword_set_data, response.data)

    return response


@pytest.mark.no_test_audit_log
@pytest.mark.django_db
def test_keywordset_cannot_have_deprecated_keyword(keyword, keyword_set):
    keyword.deprecated = True
    keyword.save()
    with pytest.raises(ValidationError):
        keyword_set.save()


@pytest.mark.django_db
def test_create_keywordset_with_post(user, api_client, keyword_set_dict):
    api_client.force_authenticate(user)

    assert_create_keyword_set(api_client, keyword_set_dict)


@pytest.mark.django_db
def test_keyword_set_id_is_audit_logged_on_post(user_api_client, keyword_set_dict):
    response = assert_create_keyword_set(user_api_client, keyword_set_dict)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data["id"]
    ]


@pytest.mark.django_db
def test_cannot_create_keywordset_with_existing_id(user, api_client, keyword_set_dict):
    api_client.force_authenticate(user)

    keyword_set_data = keyword_set_dict
    assert_create_keyword_set(api_client, keyword_set_data)

    response = create_keyword_set(api_client, keyword_set_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test__unauthenticated_user_cannot_create_keywordset(api_client, keyword_set_dict):
    api_client.force_authenticate(None)

    response = create_keyword_set(api_client, keyword_set_dict)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__non_admin_cannot_create_keywordset(api_client, keyword_set_dict, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = create_keyword_set(api_client, keyword_set_dict)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test__user_from_other_organization_cannot_create_keywordset(
    api_client, keyword_set_dict, user
):
    user.get_default_organization().regular_users.remove(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = create_keyword_set(api_client, keyword_set_dict)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_datasource_permission_missing(
    user, api_client, keyword_set_dict, other_data_source
):
    url = reverse("keywordset-list")
    api_client.force_authenticate(user)

    keyword_set_data = keyword_set_dict
    keyword_set_data["data_source"] = other_data_source.id
    response = api_client.post(url, keyword_set_data, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_with_organization_can_create_keywordset(
    api_client, keyword_set_dict, data_source, organization
):
    data_source.owner = organization
    data_source.save()

    assert_create_keyword_set(api_client, keyword_set_dict, data_source)


@pytest.mark.django_db
def test__api_key_without_organization_cannot_create_keywordset(
    api_client, keyword_set_dict, data_source
):
    response = create_keyword_set(api_client, keyword_set_dict, data_source)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_create_keywordset(api_client, keyword_set_dict):
    api_client.credentials(apikey="unknown")
    response = create_keyword_set(api_client, keyword_set_dict)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__empty_api_key_cannot_create_keywordset(api_client, keyword_set_dict):
    api_client.credentials(apikey="")
    response = create_keyword_set(api_client, keyword_set_dict)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_create_keyword(
    api_client, keyword_set_dict, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()
    api_client.force_authenticate(user)

    response = create_keyword_set(api_client, keyword_set_dict)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_editable_resources_can_create_keyword(
    api_client, keyword_set_dict, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user=user)

    assert_create_keyword_set(api_client, keyword_set_dict)
