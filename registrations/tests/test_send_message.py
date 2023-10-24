import pytest
from django.conf import settings
from django.core import mail
from django.utils import translation
from rest_framework import status

from events.models import Language
from events.tests.utils import versioned_reverse as reverse
from registrations.models import SignUp
from registrations.tests.factories import SignUpFactory, SignUpGroupFactory

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
    api_client, registration_id, send_message_data, expected_signups
):
    response = send_message(api_client, registration_id, send_message_data)

    assert response.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == len(expected_signups)
    for signup in expected_signups:
        # Find possible mails by the edit link. At the we make sure that edit link exists in the mail
        signup_edit_url = f"/registration/{registration_id}/"
        if signup.signup_group_id:
            signup_edit_url += f"signup-group/{signup.signup_group_id}/edit"
        else:
            signup_edit_url += f"signup/{signup.id}/edit"
        mails = [x for x in mail.outbox if signup_edit_url in str(x.alternatives[0])]

        assert len(mails)
        assert mails[0].subject == send_message_data["subject"]
        assert mails[0].body == send_message_data["body"]
        assert mails[0].from_email == settings.SUPPORT_EMAIL
        # signup-group can be same for multiple signups to check
        # that any of those mails has match
        assert next(x for x in mails if signup.email in x.to) is not None

    return response


# === tests ===


@pytest.mark.django_db
def test_head_method_not_allowed(user_api_client, registration):
    response = head_message(user_api_client, registration.id)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_admin_user_can_send_message_to_all_signups(
    api_client, registration, signup, signup2, user
):
    api_client.force_authenticate(user)
    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(
        api_client, registration.id, send_message_data, [signup, signup2]
    )
    # Default language for the email is Finnish
    assert "Tarkastele ilmoittautumistasi täällä" in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_email_is_sent_to_all_with_attending_status_if_no_groups_or_signups_given(
    api_client, registration, user
):
    # Group
    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        email="test@test.com",
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
    )
    second_signup = SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        responsible_for_group=True,
        email="test2@test.com",
    )

    # Individual
    third_signup = SignUpFactory(registration=registration, email="test3@test.com")
    SignUpFactory(
        registration=registration,
        email="test4@test.com",
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
    )

    api_client.force_authenticate(user)
    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(
        api_client,
        registration.id,
        send_message_data,
        [
            second_signup,
            third_signup,
        ],
    )
    # Default language for the email is Finnish
    assert "Tarkastele ilmoittautumistasi täällä" in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_email_is_sent_to_selected_signup_groups_responsible_signup_only(
    api_client, registration, user
):
    first_signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=first_signup_group,
        registration=registration,
        email="test@test.com",
    )
    SignUpFactory(
        signup_group=first_signup_group,
        registration=registration,
        responsible_for_group=True,
        email="test2@test.com",
    )

    second_signup_group = SignUpGroupFactory(registration=registration)
    third_signup = SignUpFactory(
        signup_group=second_signup_group,
        registration=registration,
        responsible_for_group=True,
        email="test3@test.com",
    )
    SignUpFactory(
        signup_group=second_signup_group,
        registration=registration,
        email="test4@test.com",
    )

    api_client.force_authenticate(user)
    send_message_data = {
        "subject": "Message subject",
        "body": "Message body",
        "signup_groups": [second_signup_group.pk],
    }

    response = assert_send_message(
        api_client, registration.id, send_message_data, [third_signup]
    )
    # Default language for the email is Finnish
    assert "Tarkastele ilmoittautumistasi täällä" in str(mail.outbox[0].alternatives[0])
    # signups should include signup who is responsible for the group
    assert response.data["signups"] == [third_signup.id]


@pytest.mark.django_db
def test_email_is_sent_to_selected_signups_only(api_client, registration, user):
    first_signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=first_signup_group,
        registration=registration,
        email="test@test.com",
    )
    responsible_signup = SignUpFactory(
        signup_group=first_signup_group,
        registration=registration,
        responsible_for_group=True,
        email="test2@test.com",
    )

    second_signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=second_signup_group,
        registration=registration,
        responsible_for_group=True,
        email="test3@test.com",
    )
    non_responsible_signup = SignUpFactory(
        signup_group=second_signup_group,
        registration=registration,
        email="test4@test.com",
    )

    individual_signup = SignUpFactory(registration=registration, email="test5@test.com")
    SignUpFactory(registration=registration, email="test6@test.com")

    api_client.force_authenticate(user)
    send_message_data = {
        "subject": "Message subject",
        "body": "Message body",
        "signups": [
            responsible_signup.pk,
            non_responsible_signup.pk,
            individual_signup.pk,
        ],
    }

    assert_send_message(
        api_client,
        registration.id,
        send_message_data,
        [
            responsible_signup,
            non_responsible_signup,
            individual_signup,
        ],
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
    api_client,
    expected_heading,
    expected_cta_button_text,
    languages,
    language_pk,
    registration,
    signup,
    user,
):
    with translation.override(language_pk):
        registration.event.name = "Foo"
        registration.event.save()
        service_language = Language.objects.get(pk=language_pk)
        signup.service_language = service_language
        signup.save()

        api_client.force_authenticate(user)
        send_message_data = {
            "subject": "Message subject",
            "body": "Message body",
            "signups": [signup.id],
        }

        assert_send_message(api_client, registration.id, send_message_data, [signup])
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
    api_client, registration, required_field, signup, signup2, user
):
    api_client.force_authenticate(user)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(
        api_client, registration.id, send_message_data, [signup, signup2]
    )

    send_message_data[required_field] = ""

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data[required_field][0].code == "blank"


@pytest.mark.django_db
def test_send_message_to_selected_signups(
    api_client, registration, signup, signup2, signup3, user
):
    api_client.force_authenticate(user)
    send_message_data = {
        "subject": "Message subject",
        "body": "Message body",
        "signups": [signup.id, signup3.id],
    }

    response = assert_send_message(
        api_client, registration.id, send_message_data, [signup, signup3]
    )
    assert response.data["signups"] == [signup.id, signup3.id]


@pytest.mark.django_db
def test_cannot_send_message_to_nonexistent_signups(
    api_client, registration, registration2, signup, signup2, user
):
    signup2.registration = registration2
    signup2.save()
    api_client.force_authenticate(user)

    send_message_data = {
        "subject": "Message subject",
        "body": "Message body",
        "signups": [signup2.id],
    }
    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0].code == "does_not_exist"


@pytest.mark.django_db
def test_cannot_send_message_with_invalid_signup_pk_type(
    api_client, registration, signup, user
):
    api_client.force_authenticate(user)
    send_message_data = {
        "subject": "Message subject",
        "body": "Message body",
        "signups": ["not-exist"],
    }

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signups"][0].code == "incorrect_type"


@pytest.mark.django_db
def test_cannot_send_message_with_invalid_signup_group_pk_type(
    api_client, registration, signup, user
):
    api_client.force_authenticate(user)
    send_message_data = {
        "subject": "Message subject",
        "body": "Message body",
        "signup_groups": ["not-exist"],
    }

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["signup_groups"][0].code == "incorrect_type"


@pytest.mark.django_db
def test_cannot_send_message_with_nonexistent_registration_id(
    api_client, organization, user
):
    api_client.force_authenticate(user)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, "nonexistent-id", send_message_data)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_unauthenticated_user_cannot_send_message(api_client, registration):
    api_client.force_authenticate(None)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_non_admin_cannot_send_message(api_client, registration, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_user_from_other_organization_cannot_send_message(
    api_client, registration, user2
):
    api_client.force_authenticate(user2)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_can_send_message_with_missing_datasource_permission(
    user_api_client, other_data_source, registration, signup
):
    registration.event.data_source = other_data_source
    registration.event.save()

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(user_api_client, registration.id, send_message_data, [signup])


@pytest.mark.django_db
def test_registration_admin_can_send_message_with_missing_datasource_permission(
    user_api_client, other_data_source, registration, signup, user
):
    user.get_default_organization().registration_admin_users.add(user)

    registration.event.data_source = other_data_source
    registration.event.save()

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(user_api_client, registration.id, send_message_data, [signup])


@pytest.mark.django_db
def test_api_key_with_organization_can_send_message(
    api_client, data_source, organization, registration, signup, signup2
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(
        api_client, registration.id, send_message_data, [signup, signup2]
    )


@pytest.mark.django_db
def test_api_key_with_wrong_data_source_cannot_send_message(
    api_client, organization, other_data_source, registration
):
    other_data_source.owner = organization
    other_data_source.save()

    api_client.credentials(apikey=other_data_source.api_key)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_unknown_api_key_cannot_send_message(api_client, registration):
    api_client.credentials(apikey="unknown")

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_empty_api_key_cannot_send_message(api_client, registration):
    api_client.credentials(apikey="")

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.django_db
def test_admin_can_send_message_regardless_of_non_user_editable_resources(
    user_api_client,
    data_source,
    organization,
    registration,
    signup,
    user_editable_resources,
):
    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(user_api_client, registration.id, send_message_data, [signup])


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.django_db
def test_registration_admin_can_send_message_regardless_of_non_user_editable_resources(
    user_api_client,
    data_source,
    organization,
    registration,
    signup,
    user,
    user_editable_resources,
):
    user.get_default_organization().registration_admin_users.add(user)

    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(user_api_client, registration.id, send_message_data, [signup])
