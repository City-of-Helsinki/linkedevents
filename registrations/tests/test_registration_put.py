import pytest
from django.core import mail
from django.utils import translation
from rest_framework import status

from events.models import Event
from events.tests.utils import versioned_reverse as reverse
from registrations.models import RegistrationUser
from registrations.tests.test_registration_post import (
    create_registration,
    get_event_url,
)

# === util methods ===


def update_registration(api_client, pk, registration_data, data_source=None):
    edit_url = reverse("registration-detail", kwargs={"pk": pk})

    if data_source:
        api_client.credentials(apikey=data_source.api_key)

    response = api_client.put(edit_url, registration_data, format="json")
    return response


def assert_update_registration(api_client, pk, registration_data, data_source=None):
    response = update_registration(api_client, pk, registration_data, data_source)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == pk


# === tests ===


@pytest.mark.django_db
def test__update_registration(api_client, event, user):
    api_client.force_authenticate(user)

    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "audience_max_age": 10,
    }

    assert_update_registration(api_client, response.data["id"], registration_data)


@pytest.mark.django_db
def test__non_admin_cannot_update_registration(api_client, event, registration, user):
    event.publisher.admin_users.remove(user)
    api_client.force_authenticate(user)

    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "audience_max_age": 10,
    }
    response = update_registration(api_client, registration.id, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__admin_can_update_registration_from_another_data_source(
    api_client, event2, other_data_source, organization, registration2, user
):
    other_data_source.owner = organization
    other_data_source.user_editable_resources = True
    other_data_source.save()
    api_client.force_authenticate(user)

    event2.publisher = organization
    event2.save()

    registration_data = {
        "event": {"@id": get_event_url(event2.id)},
        "audience_max_age": 10,
    }
    assert_update_registration(api_client, registration2.id, registration_data)


@pytest.mark.django_db
def test__correct_api_key_can_update_registration(
    api_client, event, data_source, organization, registration
):
    data_source.owner = organization
    data_source.save()

    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "audience_max_age": 10,
    }
    assert_update_registration(
        api_client, registration.id, registration_data, data_source
    )


@pytest.mark.django_db
def test__api_key_from_wrong_data_source_cannot_update_registration(
    api_client, event, organization, other_data_source, registration
):
    other_data_source.owner = organization
    other_data_source.save()

    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "audience_max_age": 10,
    }
    response = update_registration(
        api_client, registration.id, registration_data, other_data_source
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_without_organization_cannot_update_registration(
    api_client, data_source, event, registration
):
    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "audience_max_age": 10,
    }
    response = update_registration(
        api_client, registration.id, registration_data, data_source
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_update_registration(api_client, event, registration):
    api_client.credentials(apikey="unknown")

    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "audience_max_age": 10,
    }
    response = update_registration(api_client, registration.id, registration_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_update_registration(
    api_client, data_source, event, organization, registration, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()
    api_client.force_authenticate(user)

    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "audience_max_age": 10,
    }
    response = update_registration(api_client, registration.id, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_editable_resources_can_update_registration(
    api_client, data_source, event, organization, registration, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user)

    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "audience_max_age": 10,
    }
    assert_update_registration(api_client, registration.id, registration_data)


@pytest.mark.django_db
def test__admin_cannot_update_registrations_event(
    api_client, event2, registration, user
):
    """Organization admin user cannot update registration's event to an event for
    which they are not admin.
    """
    api_client.force_authenticate(user)

    registration_data = {
        "event": {"@id": get_event_url(event2.id)},
        "audience_max_age": 10,
    }
    response = update_registration(api_client, registration.id, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_send_email_to_registration_user(registration, user_api_client):
    email = "user@email.com"

    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()

        RegistrationUser.objects.create(
            registration=registration, email="delete1@email.com"
        )
        RegistrationUser.objects.create(
            registration=registration, email="delete2@email.com"
        )
        assert len(registration.registration_users.all()) == 2

        registration_data = {
            "event": {"@id": get_event_url(registration.event.id)},
            "registration_users": [{"email": email}],
        }
        assert_update_registration(user_api_client, registration.id, registration_data)
        #  assert that the email was sent
        registration_users = registration.registration_users.all()
        assert len(registration_users) == 1
        assert registration_users[0].email == email
        assert mail.outbox[0].to[0] == email
        assert mail.outbox[0].subject.startswith(
            "Oikeudet myönnetty osallistujalistaan"
        )
        assert (
            "Sähköpostiosoitteelle <strong>user@email.com</strong> on myönnetty oikeudet lukea tapahtuman <strong>Foo</strong> osallistujalista."
            in str(mail.outbox[0].alternatives[0])
        )


@pytest.mark.django_db
def test_invitation_email_is_not_sent_to_existing_registration_user(
    registration, user_api_client
):
    email = "user@email.com"

    registration_user = RegistrationUser.objects.create(
        registration=registration, email=email
    )

    registration_data = {
        "event": {"@id": get_event_url(registration.event.id)},
        "registration_users": [{"email": email}],
    }
    assert_update_registration(user_api_client, registration.id, registration_data)

    # Assert that registration user is not changed
    registration_users = registration.registration_users.all()
    assert len(registration_users) == 1
    assert registration_user.id == registration_users[0].id
    assert registration_users[0].email == email
    #  assert that the email is not sent
    assert len(mail.outbox) == 0
