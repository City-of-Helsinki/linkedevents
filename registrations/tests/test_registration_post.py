import pytest
from django.core import mail
from django.utils import translation
from rest_framework import status

from events.models import Event
from events.tests.utils import versioned_reverse as reverse
from registrations.tests.test_registration_user_invitation import (
    assert_invitation_email_is_sent,
)

# === util methods ===


def create_registration(api_client, registration_data, data_source=None):
    if data_source:
        api_client.credentials(apikey=data_source.api_key)

    create_url = reverse("registration-list")
    response = api_client.post(create_url, registration_data, format="json")
    return response


def assert_create_registration(api_client, registration_data, data_source=None):
    response = create_registration(api_client, registration_data, data_source)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["event"] == registration_data["event"]

    return response


def get_event_url(detail_pk):
    return reverse("event-detail", kwargs={"pk": detail_pk})


# === tests ===


@pytest.mark.django_db
def test_create_registration(user, api_client, event):
    api_client.force_authenticate(user)
    registration_data = {"event": {"@id": get_event_url(event.id)}}

    assert_create_registration(api_client, registration_data)


@pytest.mark.django_db
def test_only_one_registration_per_event_is_allowed(
    user, api_client, event, registration
):
    api_client.force_authenticate(user)
    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_cannot_create_registration_with_event_in_invalid_format(
    api_client, organization, user
):
    api_client.force_authenticate(user)
    registration_data = {"event": "invalid-format"}

    response = create_registration(api_client, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["event"][0] == "Incorrect JSON. Expected JSON, received str."


@pytest.mark.django_db
def test_cannot_create_registration_with_nonexistent_event(
    api_client, organization, user
):
    api_client.force_authenticate(user)
    registration_data = {"event": {"@id": "nonexistent-id"}}

    response = create_registration(api_client, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_maximum_group_size_cannot_be_less_than_one(user, api_client, event):
    api_client.force_authenticate(user)
    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "maximum_group_size": 0,
    }

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["maximum_group_size"][0].code == "min_value"


@pytest.mark.django_db
def test__unauthenticated_user_cannot_create_registration(api_client, event):
    api_client.force_authenticate(None)
    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__non_admin_cannot_create_registration(api_client, event, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_from_other_organization_cannot_create_registration(
    api_client, event, user2
):
    api_client.force_authenticate(user2)

    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_datasource_permission_missing(api_client, event, other_data_source, user):
    event.data_source = other_data_source
    event.save()
    api_client.force_authenticate(user)

    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_with_organization_can_create_registration(
    api_client, data_source, event, organization
):
    data_source.owner = organization
    data_source.save()

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    assert_create_registration(api_client, registration_data, data_source)


@pytest.mark.django_db
def test__api_key_with_wrong_data_source_cannot_create_registration(
    api_client, data_source, event, organization, other_data_source
):
    other_data_source.owner = organization
    other_data_source.save()

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    response = create_registration(api_client, registration_data, other_data_source)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_create_registration(api_client, event):
    api_client.credentials(apikey="unknown")

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__empty_api_key_cannot_create_registration(api_client, event):
    api_client.credentials(apikey="")

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_create_registration(
    api_client, data_source, event, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()
    api_client.force_authenticate(user)

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_editable_resources_can_create_registration(
    api_client, data_source, event, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user=user)

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    assert_create_registration(api_client, registration_data, data_source)


@pytest.mark.django_db
def test_send_email_to_registration_user(event, user_api_client):
    email = "user@email.com"
    event_name = "Foo"

    with translation.override("fi"):
        event.type_id = Event.TypeId.GENERAL
        event.name = event_name
        event.save()

        registration_data = {
            "event": {"@id": get_event_url(event.id)},
            "registration_users": [{"email": email}],
        }
        assert_create_registration(user_api_client, registration_data)
        #  assert that the email was sent
        assert_invitation_email_is_sent(email, event_name)
