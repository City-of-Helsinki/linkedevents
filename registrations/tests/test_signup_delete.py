import pytest
from django.core import mail
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from registrations.models import SignUp
from registrations.tests.test_registration_post import (
    assert_create_registration,
    get_event_url,
)
from registrations.tests.test_signup_post import assert_create_signup

# === util methods ===


def delete_signup(api_client, registration_pk, signup_pk, query_string=None):
    signup_url = reverse(
        "registration-signup-detail",
        kwargs={"pk": registration_pk, "signup_pk": signup_pk},
    )
    if query_string:
        signup_url = "%s?%s" % (signup_url, query_string)

    return api_client.delete(signup_url)


def assert_delete_signup(api_client, registration_pk, signup_pk, query_string=None):
    response = delete_signup(api_client, registration_pk, signup_pk, query_string)
    assert response.status_code == status.HTTP_204_NO_CONTENT


# === tests ===


@pytest.mark.django_db
def test_anonymous_user_can_delete_signup_with_cancellation_code(
    api_client, registration, signup
):
    api_client.force_authenticate(user=None)

    assert_delete_signup(
        api_client,
        registration.id,
        signup.id,
        f"cancellation_code={signup.cancellation_code}",
    )


@pytest.mark.django_db
def test_anonymous_user_cannot_delete_signup_if_cancellation_code_is_missing(
    api_client, registration, signup
):
    api_client.force_authenticate(user=None)

    response = delete_signup(api_client, registration.id, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["detail"] == "cancellation_code parameter has to be provided"


@pytest.mark.django_db
def test_cannot_delete_signup_with_wrong_cancellation_code(
    api_client, registration, signup, signup2
):
    api_client.force_authenticate(user=None)

    response = delete_signup(
        api_client,
        registration.id,
        signup.id,
        f"cancellation_code={signup2.cancellation_code}",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["detail"] == "Cancellation code did not match any signup"


@pytest.mark.django_db
def test_cannot_delete_signup_with_malformed_cancellation_code(
    api_client, registration, signup
):
    api_client.force_authenticate(user=None)

    response = delete_signup(
        api_client, registration.id, signup.id, "cancellation_code=invalid_code"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["detail"] == "Malformed UUID."


@pytest.mark.django_db
def test__admin_can_delete_signup(api_client, registration, signup, user):
    api_client.force_authenticate(user)

    assert_delete_signup(api_client, registration.id, signup.id)


@pytest.mark.django_db
def test__cannot_delete_already_deleted_signup(api_client, registration, signup, user):
    api_client.force_authenticate(user)

    assert_delete_signup(api_client, registration.id, signup.id)
    response = delete_signup(api_client, registration.id, signup.id)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test__non_admin_cannot_delete_signup(api_client, registration, signup, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = delete_signup(api_client, registration.id, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_with_organization_can_delete_signup(
    api_client, data_source, organization, registration, signup
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    assert_delete_signup(api_client, registration.id, signup.id)


@pytest.mark.django_db
def test__api_key_of_other_organization_cannot_delete_signup(
    api_client, data_source, organization2, registration, signup
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = delete_signup(api_client, registration.id, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_from_wrong_data_source_cannot_delete_signup(
    api_client, organization, other_data_source, registration, signup
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    response = delete_signup(api_client, registration.id, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_delete_signup(api_client, registration, signup):
    api_client.credentials(apikey="unknown")

    response = delete_signup(api_client, registration.id, signup.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__user_editable_resources_can_delete_signup(
    api_client, data_source, organization, registration, signup, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user)

    assert_delete_signup(api_client, registration.id, signup.id)


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_delete_signup(
    api_client, data_source, organization, registration, signup, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()
    api_client.force_authenticate(user)

    response = delete_signup(api_client, registration.id, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_signup_deletion_leads_to_changing_status_of_first_waitlisted_user(
    api_client, event, user
):
    api_client.force_authenticate(user)
    registration_data = {
        "event": {"@id": get_event_url(event.pk)},
        "maximum_attendee_capacity": 1,
    }
    response = assert_create_registration(api_client, registration_data)
    registration_id = response.data["id"]

    api_client.force_authenticate(user=None)
    sign_up_payload = {
        "registration": registration_id,
        "name": "Michael Jackson1",
        "email": "test@test.com",
    }
    response = assert_create_signup(api_client, registration_id, sign_up_payload)
    signup_id = response.data["attending"]["people"][0]["id"]
    cancellation_code = response.data["attending"]["people"][0]["cancellation_code"]

    sign_up_payload2 = {
        "registration": registration_id,
        "name": "Michael Jackson2",
        "email": "test1@test.com",
    }
    response = assert_create_signup(api_client, registration_id, sign_up_payload2)

    sign_up_payload3 = {
        "registration": registration_id,
        "name": "Michael Jackson3",
        "email": "test2@test.com",
    }
    response = assert_create_signup(api_client, registration_id, sign_up_payload3)

    assert (
        SignUp.objects.get(email=sign_up_payload["email"]).attendee_status
        == SignUp.AttendeeStatus.ATTENDING
    )
    assert (
        SignUp.objects.get(email=sign_up_payload2["email"]).attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )
    assert (
        SignUp.objects.get(email=sign_up_payload3["email"]).attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )

    assert_delete_signup(
        api_client, registration_id, signup_id, f"cancellation_code={cancellation_code}"
    )
    assert (
        SignUp.objects.get(email=sign_up_payload2["email"]).attendee_status
        == SignUp.AttendeeStatus.ATTENDING
    )
    assert (
        SignUp.objects.get(email=sign_up_payload3["email"]).attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )


@pytest.mark.django_db
def test_email_sent_on_successful_signup(api_client, registration):
    sign_up_data = {
        "name": "Michael Jackson",
        "date_of_birth": "2011-04-07",
        "email": "test@test.com",
    }
    response = assert_create_signup(api_client, registration.id, sign_up_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert sign_up_data["name"] in response.data["attending"]["people"][0]["name"]
    #  assert that the email was sent
    assert len(mail.outbox) == 1
