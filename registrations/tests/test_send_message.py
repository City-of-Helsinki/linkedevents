from collections import Counter

import pytest
from django.conf import settings
from django.core import mail
from django.utils import translation
from resilient_logger.models import ResilientLogEntry
from rest_framework import status

from events.tests.factories import ApiKeyUserFactory, LanguageFactory
from events.tests.utils import versioned_reverse as reverse
from registrations.models import SignUp
from registrations.tests.factories import (
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
)
from registrations.tests.utils import create_user_by_role

default_send_message_data: dict[str, str | list] = {
    "subject": "Message subject",
    "body": "Message body",
}


# === util methods ===


def head_message(api_client, registration_id):
    send_message_url = reverse(
        "registration-send-message", kwargs={"pk": registration_id}
    )

    return api_client.head(send_message_url)


def send_message(api_client, registration_id, send_message_data):
    send_message_url = reverse(
        "registration-send-message", kwargs={"pk": registration_id}
    )
    response = api_client.post(send_message_url, send_message_data, format="json")

    return response


def assert_send_message(
    api_client, registration_id, send_message_data, expected_contact_persons
):
    response = send_message(api_client, registration_id, send_message_data)

    assert response.status_code == status.HTTP_200_OK

    assert Counter(response.data["signups"]) == Counter(
        [
            contact_person.signup_id
            for contact_person in expected_contact_persons
            if contact_person.signup_id
        ]
    )
    assert Counter(response.data["signup_groups"]) == Counter(
        [
            contact_person.signup_group_id
            for contact_person in expected_contact_persons
            if contact_person.signup_group_id
        ]
    )

    assert len(mail.outbox) == len(expected_contact_persons)

    for contact_person in expected_contact_persons:
        # Find possible mails by the edit link. At the we make sure that edit link exists in the mail
        signup_edit_url = f"/registration/{registration_id}/"
        if contact_person.signup_group_id:
            signup_edit_url += f"signup-group/{contact_person.signup_group_id}/edit"
        else:
            signup_edit_url += f"signup/{contact_person.signup_id}/edit"
        mails = [x for x in mail.outbox if signup_edit_url in str(x.alternatives[0])]

        assert len(mails)
        assert mails[0].subject == send_message_data["subject"]
        assert mails[0].body == send_message_data["body"]
        assert mails[0].from_email == settings.SUPPORT_EMAIL
        # signup-group can be same for multiple signups to check
        # that any of those mails has match
        assert next(x for x in mails if contact_person.email in x.to) is not None

    return response


# === tests ===


@pytest.mark.django_db
def test_head_method_not_allowed(user_api_client, registration):
    response = head_message(user_api_client, registration.id)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_registration_created_admin_user_can_send_message_to_all_signups(
    user_api_client, registration, user
):
    assert registration.created_by_id == user.id

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(registration=registration, signup_group=signup_group)
    group_contact_person = SignUpContactPersonFactory(
        signup_group=signup_group,
        email="test@test.com",
    )

    signup = SignUpFactory(registration=registration)
    signup_contact_person = SignUpContactPersonFactory(
        signup=signup, email="test2@test.com"
    )

    signup2 = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.WAITING_LIST
    )
    SignUpContactPersonFactory(signup=signup2, email="test3@test.com")

    assert_send_message(
        user_api_client,
        registration.id,
        default_send_message_data,
        [group_contact_person, signup_contact_person],
    )
    # Default language for the email is Finnish
    assert "Tarkastele ilmoittautumistasi täällä" in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_registration_non_created_admin_cannot_send_message(
    user_api_client, registration, user, user2
):
    registration.created_by = user2
    registration.save(update_fields=["created_by"])

    registration.refresh_from_db()
    assert registration.created_by_id != user.id

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(registration=registration, signup_group=signup_group)
    SignUpContactPersonFactory(signup_group=signup_group, email="test@test.com")

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup, email="test2@test.com")

    signup2 = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup2, email="test3@test.com")

    response = send_message(user_api_client, registration.id, default_send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_email_is_sent_to_selected_signups_only(user_api_client, registration):
    first_signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=first_signup_group,
        registration=registration,
    )
    SignUpFactory(
        signup_group=first_signup_group,
        registration=registration,
    )
    SignUpContactPersonFactory(signup_group=first_signup_group, email="test@test.com")

    second_signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=second_signup_group,
        registration=registration,
    )
    SignUpFactory(
        signup_group=second_signup_group,
        registration=registration,
    )
    SignUpContactPersonFactory(signup_group=second_signup_group, email="test2@test.com")

    second_signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=second_signup, email="test3@test.com")

    third_signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=third_signup, email="test4@test.com")

    send_message_data = default_send_message_data.copy()
    send_message_data.update(
        {
            "signups": [second_signup.pk],
            "signup_groups": [first_signup_group.pk],
        }
    )

    assert_send_message(
        user_api_client,
        registration.id,
        send_message_data,
        [second_signup.contact_person, first_signup_group.contact_person],
    )
    # Default language for the email is Finnish
    assert "Tarkastele ilmoittautumistasi täällä" in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "language_pk, expected_heading, expected_cta_button_text",
    [
        (
            "en",
            "A message about the event Foo.",
            "Check your registration here",
        ),
        (
            "fi",
            "Viesti tapahtumasta Foo.",
            "Tarkastele ilmoittautumistasi täällä",
        ),
        (
            "sv",
            "Ett meddelande om evenemanget Foo.",
            "Kontrollera din registrering här",
        ),
    ],
)
@pytest.mark.django_db
def test_email_is_sent_in_signup_service_language(
    user_api_client,
    expected_heading,
    expected_cta_button_text,
    language_pk,
    registration,
    signup,
):
    LanguageFactory(pk=language_pk, service_language=True)

    with translation.override(language_pk):
        registration.event.name = "Foo"
        registration.event.save()
        signup.contact_person.service_language_id = language_pk
        signup.contact_person.save(update_fields=["service_language_id"])

        send_message_data = default_send_message_data.copy()
        send_message_data.update(
            {
                "signups": [signup.id],
            }
        )

        assert_send_message(
            user_api_client, registration.id, send_message_data, [signup.contact_person]
        )
        assert expected_heading in str(mail.outbox[0].alternatives[0])
        assert expected_cta_button_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "required_field",
    [
        "subject",
        "body",
    ],
)
@pytest.mark.django_db
def test_required_fields_has_to_be_filled(
    user_api_client, registration, required_field, signup
):
    send_message_data = default_send_message_data.copy()
    send_message_data[required_field] = ""

    response = send_message(user_api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data[required_field][0].code == "blank"


@pytest.mark.django_db
def test_cannot_send_message_to_nonexistent_signups(
    user_api_client, registration, registration2, signup
):
    signup2 = SignUpFactory(registration=registration2)

    send_message_data = default_send_message_data.copy()
    send_message_data.update(
        {
            "signups": [signup2.id],
        }
    )

    response = send_message(user_api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0].code == "does_not_exist"


@pytest.mark.parametrize("payload_key", ["signups", "signup_groups"])
@pytest.mark.django_db
def test_cannot_send_message_with_invalid_signup_pk_type(
    user_api_client, registration, signup, payload_key
):
    send_message_data = default_send_message_data.copy()
    send_message_data.update(
        {
            payload_key: ["not-exist"],
        }
    )

    response = send_message(user_api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data[payload_key][0].code == "incorrect_type"


@pytest.mark.django_db
def test_cannot_send_message_with_nonexistent_registration_id(
    user_api_client, organization
):
    response = send_message(
        user_api_client, "nonexistent-id", default_send_message_data
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_unauthenticated_user_cannot_send_message(api_client, registration):
    response = send_message(api_client, registration.id, default_send_message_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("user_role", ["financial_admin", "regular_user"])
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_send_message(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    response = send_message(api_client, registration.id, default_send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_user_from_other_organization_cannot_send_message(
    api_client, registration, user2
):
    api_client.force_authenticate(user2)

    response = send_message(api_client, registration.id, default_send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("user_role", ["admin", "registration_admin"])
@pytest.mark.django_db
def test_admin_or_registration_admin_can_send_message_with_missing_datasource_permission(
    api_client, other_data_source, registration, signup, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    if user_role == "admin":
        registration.created_by = user
        registration.save(update_fields=["created_by"])

    registration.event.data_source = other_data_source
    registration.event.save(update_fields=["data_source"])

    assert_send_message(
        api_client, registration.id, default_send_message_data, [signup.contact_person]
    )


@pytest.mark.django_db
def test_registration_created_api_key_with_organization_can_send_message(
    api_client, data_source, organization, registration, signup, signup2
):
    apikey_user = ApiKeyUserFactory(data_source=data_source)

    registration.created_by = apikey_user
    registration.save(update_fields=["created_by"])

    data_source.owner = organization
    data_source.save(update_fields=["owner"])
    api_client.credentials(apikey=data_source.api_key)

    assert_send_message(
        api_client,
        registration.id,
        default_send_message_data,
        [signup.contact_person, signup2.contact_person],
    )


@pytest.mark.django_db
def test_registration_non_created_api_key_with_organization_cannot_send_message(
    api_client, data_source, organization, registration, signup, signup2
):
    data_source.owner = organization
    data_source.save(update_fields=["owner"])
    api_client.credentials(apikey=data_source.api_key)

    response = send_message(api_client, registration.id, default_send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_with_wrong_data_source_cannot_send_message(
    api_client, organization, other_data_source, registration
):
    other_data_source.owner = organization
    other_data_source.save()

    api_client.credentials(apikey=other_data_source.api_key)

    response = send_message(api_client, registration.id, default_send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("api_key", ["", "unknown"])
@pytest.mark.django_db
def test_invalid_api_key_cannot_send_message(api_client, registration, api_key):
    api_client.credentials(apikey=api_key)

    response = send_message(api_client, registration.id, default_send_message_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.parametrize("user_role", ["admin", "registration_admin"])
@pytest.mark.django_db
def test_admin_or_registration_admin_can_send_message_regardless_of_user_editable_resources(
    api_client,
    data_source,
    organization,
    registration,
    signup,
    user_editable_resources,
    user_role,
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    if user_role == "admin":
        registration.created_by = user
        registration.save(update_fields=["created_by"])

    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    assert_send_message(
        api_client, registration.id, default_send_message_data, [signup.contact_person]
    )


@pytest.mark.django_db
def test_send_message_no_contact_persons_found(user_api_client, registration):
    first_signup_group = SignUpGroupFactory(registration=registration)
    SignUpContactPersonFactory(signup_group=first_signup_group, email=None)

    second_signup_group = SignUpGroupFactory(registration=registration)
    SignUpContactPersonFactory(signup_group=second_signup_group, email="")

    first_signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=first_signup, email=None)

    second_signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=second_signup, email="")

    response = send_message(user_api_client, registration.id, default_send_message_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_signup_ids_are_audit_logged_on_send_message(
    user_api_client, registration, signup, signup2
):
    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(
        user_api_client,
        registration.id,
        send_message_data,
        [signup.contact_person, signup2.contact_person],
    )

    audit_log_entry = ResilientLogEntry.objects.first()
    assert Counter(audit_log_entry.context["target"]["object_ids"]) == Counter(
        [signup.contact_person.pk, signup2.contact_person.pk]
    )


@pytest.mark.django_db
def test_cannot_send_message_to_soft_deleted_signups(user_api_client, registration):
    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup, email="test@test.com")
    signup.soft_delete()

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpContactPersonFactory(signup_group=signup_group, email="test-group@test.com")
    signup_group.soft_delete()

    send_message_data = default_send_message_data.copy()
    send_message_data.update(
        {
            "signups": [signup.id],
            "signup_groups": [signup_group.id],
        }
    )

    response = send_message(user_api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0].code == "does_not_exist"
    assert response.data["signup_groups"][0].code == "does_not_exist"
