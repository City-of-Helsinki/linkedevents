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
from registrations.tests.test_registration_user_invitation import (
    assert_invitation_email_is_sent,
)

email = "user@email.com"
edited_email = "edited@email.com"
event_name = "Foo"

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
    return response


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
def test__send_email_to_new_registration_user(registration, user_api_client):
    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = event_name
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
        response = assert_update_registration(
            user_api_client, registration.id, registration_data
        )
        #  assert that registration user was created
        registration_users = response.data["registration_users"]
        assert len(registration_users) == 1
        assert registration_users[0]["email"] == email
        #  assert that the email was sent
        assert_invitation_email_is_sent(email, event_name)


@pytest.mark.django_db
def test__email_is_not_sent_if_registration_user_email_is_not_updated(
    registration, user_api_client
):
    registration_user = RegistrationUser.objects.create(
        registration=registration, email=email
    )

    registration_data = {
        "event": {"@id": get_event_url(registration.event.id)},
        "registration_users": [{"id": registration_user.id, "email": email}],
    }
    assert_update_registration(user_api_client, registration.id, registration_data)

    # Assert that registration user is not changed
    registration_users = registration.registration_users.all()
    assert len(registration_users) == 1
    assert registration_user.id == registration_users[0].id
    assert registration_users[0].email == email
    #  assert that the email is not sent
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test__email_is_sent_if_registration_user_email_is_updated(
    registration, user_api_client
):
    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = event_name
        registration.event.save()

        registration_user = RegistrationUser.objects.create(
            registration=registration, email=email
        )

        registration_data = {
            "event": {"@id": get_event_url(registration.event.id)},
            "registration_users": [{"id": registration_user.id, "email": edited_email}],
        }
        assert_update_registration(user_api_client, registration.id, registration_data)
        #  assert that the email was sent
        assert_invitation_email_is_sent(edited_email, event_name)


@pytest.mark.django_db
def test__cannot_update_registration_user_with_invalid_id(
    registration, user_api_client
):
    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = event_name
        registration.event.save()

        RegistrationUser.objects.create(registration=registration, email=email)

        registration_data = {
            "event": {"@id": get_event_url(registration.event.id)},
            "registration_users": [{"id": "invalid", "email": edited_email}],
        }
        response = update_registration(
            user_api_client, registration.id, registration_data
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["registration_users"][0]["id"][0].code == "incorrect_type"


@pytest.mark.django_db
def test__cannot_update_registration_user_with_unexisting_id(
    registration, user_api_client
):
    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = event_name
        registration.event.save()

        RegistrationUser.objects.create(registration=registration, email=email)

        registration_data = {
            "event": {"@id": get_event_url(registration.event.id)},
            "registration_users": [{"id": 1234567, "email": edited_email}],
        }
        response = update_registration(
            user_api_client, registration.id, registration_data
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["registration_users"][0]["id"][0].code == "does_not_exist"


@pytest.mark.django_db
def test__cannot_update_registration_user_with_duplicate_email(
    registration, user_api_client
):
    email1 = "email1@test.fi"
    email2 = "email2@test.fi"

    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = event_name
        registration.event.save()

        registration_user1 = RegistrationUser.objects.create(
            registration=registration, email=email1
        )
        registration_user2 = RegistrationUser.objects.create(
            registration=registration, email=email2
        )

        registration_data = {
            "event": {"@id": get_event_url(registration.event.id)},
            "registration_users": [
                {"id": registration_user1.id, "email": email2},
                {"id": registration_user2.id, "email": email1},
            ],
        }

        response = update_registration(
            user_api_client, registration.id, registration_data
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["registration_users"][0].code == "unique"
