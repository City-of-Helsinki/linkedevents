import pytest
from django.conf import settings

from audit_log.models import AuditLogEntry
from events.auth import ApiKeyUser
from events.tests.utils import assert_place_data_is_equal

from .utils import versioned_reverse as reverse

# === util methods ===


def create_with_post(api_client, place_data, data_source=None, version="v1"):
    create_url = reverse("places-list", version=version)
    if data_source:
        api_client.credentials(apikey=data_source.api_key)

    # save with post
    response = api_client.post(create_url, place_data, format="json")
    assert response.status_code == 201, str(response.content)

    # double-check with get
    resp2 = api_client.get(response.data["@id"])
    assert resp2.status_code == 200, str(response.content)

    return resp2


# === tests ===


@pytest.mark.parametrize(
    "user2_with_user_type",
    ["org_admin", "superuser"],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_create_place_with_post(api_client, place_dict, user2_with_user_type):
    api_client.force_authenticate(user2_with_user_type)

    response = create_with_post(api_client, place_dict)
    assert_place_data_is_equal(place_dict, response.data)


@pytest.mark.django_db
def test_place_id_is_audit_logged_on_post(user_api_client, place_dict):
    response = create_with_post(user_api_client, place_dict)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data["id"]
    ]


@pytest.mark.django_db
def test_cannot_create_an_place_with_existing_id(api_client, place_dict, user):
    api_client.force_authenticate(user=user)
    place_dict["id"] = settings.SYSTEM_DATA_SOURCE_ID + ":1"
    create_with_post(api_client, place_dict)
    response2 = api_client.post(reverse("places-list"), place_dict, format="json")
    assert response2.status_code == 400


@pytest.mark.django_db
def test_a_non_user_cannot_create_a_place(api_client, place_dict):
    response = api_client.post(reverse("places-list"), place_dict, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_a_non_admin_cannot_create_a_place(api_client, place_dict, user):
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = api_client.post(reverse("places-list"), place_dict, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_api_key_with_organization_can_create_a_place(
    api_client, place_dict, data_source, organization
):
    data_source.owner = organization
    data_source.save()

    response = create_with_post(api_client, place_dict, data_source)
    assert_place_data_is_equal(place_dict, response.data)
    assert ApiKeyUser.objects.all().count() == 1


@pytest.mark.django_db
def test_api_key_without_organization_cannot_create_a_place(
    api_client, place_dict, data_source
):
    api_client.credentials(apikey=data_source.api_key)
    response = api_client.post(reverse("places-list"), place_dict, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_unknown_api_key_cannot_create_a_place(api_client, place_dict):
    api_client.credentials(apikey="unknown")
    response = api_client.post(reverse("places-list"), place_dict, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_empty_api_key_cannot_create_a_place(api_client, place_dict):
    api_client.credentials(apikey="")
    response = api_client.post(reverse("places-list"), place_dict, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_non_user_editable_resources_cannot_create_a_place(
    api_client, place, place_dict, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()
    api_client.force_authenticate(user=user)
    response = api_client.post(reverse("places-list"), place_dict, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_user_editable_resources_can_create_a_place(
    api_client, place, place_dict, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user=user)
    response = api_client.post(reverse("places-list"), place_dict, format="json")
    assert response.status_code == 201
