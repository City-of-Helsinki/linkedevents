import pytest
from django.core import mail
from django.utils import translation
from rest_framework import status

from events.models import Event, Language
from events.tests.utils import versioned_reverse as reverse
from registrations.models import RegistrationUserAccess

email = "user@email.com"
event_name = "Foo"

# === util methods ===


def send_invitation(api_client, pk):
    send_invitation_url = reverse(
        "registrationuseraccess-send-invitation",
        kwargs={"pk": pk},
    )
    response = api_client.post(send_invitation_url)

    return response


def assert_send_invitation(api_client, pk):
    response = send_invitation(api_client, pk)

    assert response.status_code == status.HTTP_200_OK


def assert_invitation_email_is_sent(email, event_name):
    assert mail.outbox[0].to[0] == email
    assert mail.outbox[0].subject.startswith("Oikeudet myönnetty osallistujalistaan")
    assert (
        f"Sähköpostiosoitteelle <strong>{email}</strong> on myönnetty oikeudet lukea tapahtuman <strong>{event_name}</strong> osallistujalista."
        in str(mail.outbox[0].alternatives[0])
    )


# === tests ===


@pytest.mark.django_db
def test_admin_user_can_send_invitation_to_registration_user_access(
    registration, user_api_client
):
    with translation.override("fi"):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = event_name
        registration.event.save()
        registration_user_access = RegistrationUserAccess.objects.create(
            registration=registration, email=email
        )

        assert_send_invitation(user_api_client, registration_user_access.pk)
        assert_invitation_email_is_sent(email, event_name)


@pytest.mark.django_db
def test_anonymous_user_cannot_send_invitation_to_registration_user_access(
    api_client, registration
):
    registration_user_access = RegistrationUserAccess.objects.create(
        registration=registration, email=email
    )

    response = send_invitation(api_client, registration_user_access.pk)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_regular_user_cannot_send_invitation_to_registration_user_access(
    registration, user, user_api_client
):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    registration_user_access = RegistrationUserAccess.objects.create(
        registration=registration, email=email
    )

    response = send_invitation(user_api_client, registration_user_access.pk)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    "language_pk,expect_subject,expect_content",
    [
        (
            "en",
            "Rights granted to the participant list",
            f"The e-mail address <strong>{email}</strong> has been granted the rights to read the participant list of the event <strong>{event_name}</strong>.",
        ),
        (
            "fi",
            "Oikeudet myönnetty osallistujalistaan",
            f"Sähköpostiosoitteelle <strong>{email}</strong> on myönnetty oikeudet lukea tapahtuman <strong>{event_name}</strong> osallistujalista.",
        ),
        (
            "sv",
            "Rättigheter tilldelade deltagarlistan",
            f"E-postadressen <strong>{email}</strong> har beviljats rättigheter att läsa deltagarlistan för evenemanget <strong>{event_name}</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_invitation_to_send_in_selected_language(
    expect_content,
    expect_subject,
    language_pk,
    languages,
    registration,
    user_api_client,
):
    with translation.override(language_pk):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = event_name
        registration.event.save()

        language = Language.objects.get(pk=language_pk)
        registration_user_access = RegistrationUserAccess.objects.create(
            registration=registration, email=email, language=language
        )

        assert_send_invitation(user_api_client, registration_user_access.pk)
        assert mail.outbox[0].to[0] == email
        assert mail.outbox[0].subject.startswith(expect_subject)
        assert expect_content in str(mail.outbox[0].alternatives[0])
