import pytest
from django.core import mail
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from registrations.models import SeatReservationCode, SignUp
from registrations.tests.test_signup_post import assert_create_signups

# === util methods ===


def delete_signup(api_client, signup_pk, query_string=None):
    signup_url = reverse(
        "signup-detail",
        kwargs={"pk": signup_pk},
    )
    if query_string:
        signup_url = "%s?%s" % (signup_url, query_string)

    return api_client.delete(signup_url)


def assert_delete_signup(api_client, signup_pk, query_string=None):
    response = delete_signup(api_client, signup_pk, query_string)
    assert response.status_code == status.HTTP_204_NO_CONTENT


# === tests ===


@pytest.mark.django_db
def test_anonymous_user_can_delete_signup_with_cancellation_code(
    api_client, registration, signup
):
    api_client.force_authenticate(user=None)

    assert_delete_signup(
        api_client,
        signup.id,
        f"cancellation_code={signup.cancellation_code}",
    )


@pytest.mark.django_db
def test_anonymous_user_cannot_delete_signup_if_cancellation_code_is_missing(
    api_client, registration, signup
):
    api_client.force_authenticate(user=None)

    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["detail"] == "cancellation_code parameter has to be provided"


@pytest.mark.django_db
def test_cannot_delete_signup_with_wrong_cancellation_code(
    api_client, registration, signup, signup2
):
    api_client.force_authenticate(user=None)

    response = delete_signup(
        api_client,
        signup.id,
        f"cancellation_code={signup2.cancellation_code}",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["detail"] == "Cancellation code did not match"


@pytest.mark.django_db
def test_cannot_delete_signup_with_malformed_cancellation_code(
    api_client, registration, signup
):
    api_client.force_authenticate(user=None)

    response = delete_signup(api_client, signup.id, "cancellation_code=invalid_code")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["detail"] == "Cancellation code did not match"


@pytest.mark.django_db
def test__admin_can_delete_signup(api_client, registration, signup, user):
    api_client.force_authenticate(user)

    assert_delete_signup(api_client, signup.id)


@pytest.mark.django_db
def test_email_sent_on_successful_signup_deletion(
    api_client, registration, signup, user
):
    api_client.force_authenticate(user)

    assert_delete_signup(api_client, signup.id)
    #  assert that the email was sent
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test__cannot_delete_already_deleted_signup(api_client, registration, signup, user):
    api_client.force_authenticate(user)

    assert_delete_signup(api_client, signup.id)
    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test__non_admin_cannot_delete_signup(api_client, registration, signup, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_with_organization_can_delete_signup(
    api_client, data_source, organization, registration, signup
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    assert_delete_signup(api_client, signup.id)


@pytest.mark.django_db
def test__api_key_of_other_organization_cannot_delete_signup(
    api_client, data_source, organization2, registration, signup
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_from_wrong_data_source_cannot_delete_signup(
    api_client, organization, other_data_source, registration, signup
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_delete_signup(api_client, registration, signup):
    api_client.credentials(apikey="unknown")

    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__user_editable_resources_can_delete_signup(
    api_client, data_source, organization, registration, signup, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user)

    assert_delete_signup(api_client, signup.id)


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_delete_signup(
    api_client, data_source, organization, registration, signup, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()
    api_client.force_authenticate(user)

    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_signup_deletion_leads_to_changing_status_of_first_waitlisted_user(
    api_client, event, registration, user
):
    api_client.force_authenticate(user)
    registration.audience_max_age = None
    registration.audience_min_age = None
    registration.maximum_attendee_capacity = 1
    registration.save()

    api_client.force_authenticate(user=None)

    reservation = SeatReservationCode.objects.create(registration=registration, seats=1)
    signup_data = {
        "name": "Michael Jackson1",
        "email": "test@test.com",
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }
    response = assert_create_signups(api_client, signups_data)
    signup_id = response.data["attending"]["people"][0]["id"]
    cancellation_code = response.data["attending"]["people"][0]["cancellation_code"]

    reservation2 = SeatReservationCode.objects.create(
        registration=registration, seats=1
    )
    signup_data2 = {
        "name": "Michael Jackson2",
        "email": "test1@test.com",
    }
    signups_data2 = {
        "registration": registration.id,
        "reservation_code": reservation2.code,
        "signups": [signup_data2],
    }
    assert_create_signups(api_client, signups_data2)

    reservation3 = SeatReservationCode.objects.create(
        registration=registration, seats=1
    )
    signup_data3 = {
        "name": "Michael Jackson3",
        "email": "test2@test.com",
    }
    signups_data3 = {
        "registration": registration.id,
        "reservation_code": reservation3.code,
        "signups": [signup_data3],
    }
    assert_create_signups(api_client, signups_data3)

    assert (
        SignUp.objects.get(email=signup_data["email"]).attendee_status
        == SignUp.AttendeeStatus.ATTENDING
    )
    assert (
        SignUp.objects.get(email=signup_data2["email"]).attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )
    assert (
        SignUp.objects.get(email=signup_data3["email"]).attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )

    assert_delete_signup(
        api_client, signup_id, f"cancellation_code={cancellation_code}"
    )
    assert (
        SignUp.objects.get(email=signup_data2["email"]).attendee_status
        == SignUp.AttendeeStatus.ATTENDING
    )
    assert (
        SignUp.objects.get(email=signup_data3["email"]).attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )
