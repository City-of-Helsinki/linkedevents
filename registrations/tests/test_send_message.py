import pytest
from django.conf import settings
from django.core import mail
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse


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


@pytest.mark.django_db
def test_admin_user_can_send_message_to_all_signups(
    api_client, registration, signup, signup2, user
):
    api_client.force_authenticate(user)
    send_message_data = {"subject": "Message subject", "body": "Message body"}

    assert_send_message(
        api_client, registration.id, send_message_data, [signup.email, signup2.email]
    )


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
    assert str(response.data[required_field]) == "This field must be specified."


@pytest.mark.django_db
def test_send_message_to_selected_signups(
    api_client, registration, signup, signup2, user
):
    api_client.force_authenticate(user)
    send_message_data = {
        "subject": "Message subject",
        "body": "Message body",
        "signups": [signup.id],
    }

    assert_send_message(api_client, registration.id, send_message_data, [signup.email])


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
