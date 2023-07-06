import pytest
from django.core import mail
from django.utils import translation
from rest_framework import status

from events.models import Event
from events.tests.utils import versioned_reverse as reverse
from registrations.models import RegistrationUser

# === util methods ===


def send_invitation(api_client, pk):
    send_invitation_url = reverse(
        "registrationuser-send-invitation",
        kwargs={"pk": pk},
    )
    response = api_client.post(send_invitation_url)

    return response


def assert_send_invitation(api_client, pk):
    response = send_invitation(api_client, pk)

    assert response.status_code == status.HTTP_200_OK


# === tests ===


@pytest.mark.django_db
def test_admin_user_can_send_invitation_to_registration_user(
    registration, user_api_client
):
    email = "user@email.com"

    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()
        registration_user = RegistrationUser.objects.create(
            registration=registration, email=email
        )

        assert_send_invitation(user_api_client, registration_user.pk)
        assert mail.outbox[0].to[0] == email
        assert mail.outbox[0].subject.startswith(
            "Oikeudet myönnetty osallistujalistaan"
        )
        assert (
            "Sähköpostiosoitteelle <strong>user@email.com</strong> on myönnetty oikeudet lukea tapahtuman <strong>Foo</strong> osallistujalista."
            in str(mail.outbox[0].alternatives[0])
        )


@pytest.mark.django_db
def test_anonymous_user_cannot_send_invitation_to_registration_user(
    api_client, registration
):
    email = "user@email.com"
    registration_user = RegistrationUser.objects.create(
        registration=registration, email=email
    )

    response = send_invitation(api_client, registration_user.pk)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_regular_user_cannot_send_invitation_to_registration_user(
    registration, user, user_api_client
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    email = "user@email.com"
    registration_user = RegistrationUser.objects.create(
        registration=registration, email=email
    )

    response = send_invitation(user_api_client, registration_user.pk)
    assert response.status_code == status.HTTP_403_FORBIDDEN
