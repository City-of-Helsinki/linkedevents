import pytest
from django.utils import translation
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event, Language
from events.tests.utils import versioned_reverse as reverse
from registrations.models import RegistrationUserAccess
from registrations.tests.factories import RegistrationUserAccessFactory
from registrations.tests.utils import (
    assert_invitation_email_is_sent,
    create_user_by_role,
)

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
        assert_invitation_email_is_sent(email, event_name, registration_user_access)


@pytest.mark.django_db
def test_anonymous_user_cannot_send_invitation_to_registration_user_access(
    api_client, registration
):
    registration_user_access = RegistrationUserAccess.objects.create(
        registration=registration, email=email
    )

    response = send_invitation(api_client, registration_user_access.pk)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("user_role", ["financial_admin", "regular_user"])
@pytest.mark.django_db
def test_not_allowed_roles_cannot_send_invitation_to_registration_user_access(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    registration_user_access = RegistrationUserAccess.objects.create(
        registration=registration, email=email
    )

    response = send_invitation(api_client, registration_user_access.pk)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    "language_pk,is_substitute_user,expect_subject,expect_content",
    [
        (
            "en",
            False,
            "Rights granted to the participant list",
            f"The e-mail address <strong>{email}</strong> has been granted the rights "
            f"to read the participant list of the event <strong>{event_name}</strong>.",
        ),
        (
            "fi",
            False,
            "Oikeudet myönnetty osallistujalistaan",
            f"Sähköpostiosoitteelle <strong>{email}</strong> on myönnetty oikeudet "
            f"lukea tapahtuman <strong>{event_name}</strong> osallistujalista.",
        ),
        (
            "sv",
            False,
            "Rättigheter tilldelade deltagarlistan",
            f"E-postadressen <strong>{email}</strong> har beviljats rättigheter att "
            f"läsa deltagarlistan för evenemanget <strong>{event_name}</strong>.",
        ),
        (
            "en",
            True,
            "Rights granted to the registration",
            f"The e-mail address <strong>{email}</strong> has been granted substitute user rights "
            f"to the registration of the event <strong>{event_name}</strong>.",
        ),
        (
            "fi",
            True,
            "Oikeudet myönnetty ilmoittautumiseen",
            f"Sähköpostiosoitteelle <strong>{email}</strong> on myönnetty sijaisen käyttöoikeudet "
            f"tapahtuman <strong>{event_name}</strong> ilmoittautumiselle.",
        ),
        (
            "sv",
            True,
            "Rättigheter beviljade till registreringen",
            f"E-postadressen <strong>{email}</strong> har beviljats ersättningsanvändarrättigheter "
            f"till registreringen av evenemanget <strong>{event_name}</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_invitation_to_send_in_selected_language(
    expect_content,
    expect_subject,
    is_substitute_user,
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
        registration_user_access = RegistrationUserAccessFactory(
            registration=registration,
            email=email,
            language=language,
            is_substitute_user=is_substitute_user,
        )

        assert_send_invitation(user_api_client, registration_user_access.pk)

        assert_invitation_email_is_sent(
            email,
            "",
            registration_user_access,
            language_pk,
            expect_subject,
            expect_content,
        )


@pytest.mark.django_db
def test_registration_user_access_id_is_audit_logged_on_invitation(
    user_api_client, registration
):
    registration_user_access = RegistrationUserAccessFactory(
        email=email, registration=registration
    )

    assert_send_invitation(user_api_client, registration_user_access.pk)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        registration_user_access.pk
    ]
