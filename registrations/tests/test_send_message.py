import pytest
from django.conf import settings
from django.core import mail
from rest_framework import status

from events.models import Language
from events.tests.utils import versioned_reverse as reverse
from registrations.tests.factories import SignUpFactory, SignUpGroupFactory


def send_message(api_client, registration_id, send_message_data):
    send_message_url = reverse(
        "registration-send-message", kwargs={"pk": registration_id}
    )
    response = api_client.post(send_message_url, send_message_data, format="json")

    return response


def assert_send_message(
    api_client, registration_id, send_message_data, expected_emails
):
    response = send_message(api_client, registration_id, send_message_data)

    assert response.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == len(expected_emails)
    valid_emails = [mail.to for mail in mail.outbox]
    for idx, email in enumerate(expected_emails):
        assert mail.outbox[idx].subject == send_message_data["subject"]
        assert mail.outbox[idx].body == send_message_data["body"]
        assert mail.outbox[idx].from_email == settings.SUPPORT_EMAIL
        assert [email] in valid_emails

    return response


@pytest.mark.django_db
def test_admin_user_can_send_message_to_all_signups(
    api_client, registration, signup, signup2, user
):
    api_client.force_authenticate(user)
    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(
        api_client, registration.id, send_message_data, [signup.email, signup2.email]
    )
    # Default language for the email is Finnish
    assert "Tarkastele ilmoittautumistasi täällä" in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_email_is_sent_to_all_if_no_groups_or_signups_given(
    api_client, registration, user
):
    # Group
    signup_group = SignUpGroupFactory(registration=registration)
    first_signup = SignUpFactory(
        signup_group=signup_group, registration=registration, email="test@test.com"
    )
    second_signup = SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        responsible_for_group=True,
        email="test2@test.com",
    )

    # Individual
    third_signup = SignUpFactory(registration=registration, email="test3@test.com")
    fourth_signup = SignUpFactory(registration=registration, email="test3@test.com")

    api_client.force_authenticate(user)
    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(
        api_client,
        registration.id,
        send_message_data,
        [
            first_signup.email,
            second_signup.email,
            third_signup.email,
            fourth_signup.email,
        ],
    )
    # Default language for the email is Finnish
    assert "Tarkastele ilmoittautumistasi täällä" in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_email_is_sent_to_selected_signup_groups_only(api_client, registration, user):
    signup_group0 = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group0, registration=registration, email="test@test.com"
    )
    SignUpFactory(
        signup_group=signup_group0,
        registration=registration,
        responsible_for_group=True,
        email="test2@test.com",
    )

    signup_group1 = SignUpGroupFactory(registration=registration)
    third_signup = SignUpFactory(
        signup_group=signup_group1,
        registration=registration,
        responsible_for_group=True,
        email="test3@test.com",
    )
    SignUpFactory(
        signup_group=signup_group1, registration=registration, email="test4@test.com"
    )

    api_client.force_authenticate(user)
    send_message_data = {
        "subject": "Message subject",
        "body": "Message body",
        "signup_groups": [signup_group1.pk],
    }

    assert_send_message(
        api_client, registration.id, send_message_data, [third_signup.email]
    )
    # Default language for the email is Finnish
    assert "Tarkastele ilmoittautumistasi täällä" in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_email_is_sent_to_selected_signups_only(api_client, registration, user):
    signup_group0 = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group0, registration=registration, email="test@test.com"
    )
    responsible_signup = SignUpFactory(
        signup_group=signup_group0,
        registration=registration,
        responsible_for_group=True,
        email="test2@test.com",
    )

    signup_group1 = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group1,
        registration=registration,
        responsible_for_group=True,
        email="test3@test.com",
    )
    non_responsible_signup = SignUpFactory(
        signup_group=signup_group1, registration=registration, email="test4@test.com"
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
            responsible_signup.email,
            non_responsible_signup.email,
            individual_signup.email,
        ],
    )
    # Default language for the email is Finnish
    assert "Tarkastele ilmoittautumistasi täällä" in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "language_pk,expect_cta_button_text",
    [
        ("en", "Check your registration here"),
        ("fi", "Tarkastele ilmoittautumistasi täällä"),
        ("sv", "Kontrollera din registrering här"),
    ],
)
@pytest.mark.django_db
def test_email_is_sent_in_signup_service_language(
    api_client,
    expect_cta_button_text,
    languages,
    language_pk,
    registration,
    signup,
    user,
):
    service_language = Language.objects.get(pk=language_pk)
    signup.service_language = service_language
    signup.save()

    api_client.force_authenticate(user)
    send_message_data = {
        "subject": "Message subject",
        "body": "Message body",
        "signups": [signup.id],
    }

    assert_send_message(api_client, registration.id, send_message_data, [signup.email])
    assert expect_cta_button_text in str(mail.outbox[0].alternatives[0])


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
        api_client, registration.id, send_message_data, [signup.email, signup2.email]
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
        api_client, registration.id, send_message_data, [signup.email, signup3.email]
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
def test__unauthenticated_user_cannot_send_message(api_client, registration):
    api_client.force_authenticate(None)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__non_admin_cannot_send_message(api_client, registration, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_from_other_organization_cannot_send_message(
    api_client, registration, user2
):
    api_client.force_authenticate(user2)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_cannot_send_message_if_missing_datasource_permission(
    api_client, other_data_source, registration, user
):
    registration.event.data_source = other_data_source
    registration.event.save()
    api_client.force_authenticate(user)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_with_organization_can_send_message(
    api_client, data_source, organization, registration, signup, signup2
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(
        api_client, registration.id, send_message_data, [signup.email, signup2.email]
    )


@pytest.mark.django_db
def test__api_key_with_wrong_data_source_cannot_send_message(
    api_client, organization, other_data_source, registration
):
    other_data_source.owner = organization
    other_data_source.save()

    api_client.credentials(apikey=other_data_source.api_key)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_send_message(api_client, registration):
    api_client.credentials(apikey="unknown")

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__empty_api_key_cannot_send_message(api_client, registration):
    api_client.credentials(apikey="")

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_send_message(
    api_client, data_source, organization, registration, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()
    api_client.force_authenticate(user)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    response = send_message(api_client, registration.id, send_message_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_editable_resources_can_create_registration(
    api_client, data_source, organization, registration, signup, signup2, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user=user)

    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(
        api_client, registration.id, send_message_data, [signup.email, signup2.email]
    )
