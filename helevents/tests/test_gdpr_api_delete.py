from unittest.mock import patch
from uuid import UUID

import pytest
import requests_mock
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from events.tests.conftest import APIClient
from events.tests.factories import EventFactory
from helevents.models import User
from helevents.tests.conftest import get_api_token_for_user_with_scopes
from helevents.tests.factories import UserFactory
from registrations.models import (
    SignUp,
    SignUpContactPerson,
    SignUpGroup,
    SignUpGroupProtectedData,
    SignUpPayment,
    SignUpProtectedData,
)
from registrations.tests.factories import (
    RegistrationFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpGroupProtectedDataFactory,
    SignUpPaymentFactory,
    SignUpProtectedDataFactory,
)

# === util methods ===


def _delete_gdpr_data(api_client: APIClient, user_uuid: UUID):
    gdpr_profile_url = reverse("helsinki_gdpr:gdpr_v1", kwargs={"uuid": user_uuid})
    return api_client.delete(gdpr_profile_url)


def _create_default_data(created_by_user):
    registration = RegistrationFactory()

    signup_group = SignUpGroupFactory(
        registration=registration, created_by=created_by_user
    )
    first_signup = SignUpFactory(
        signup_group=signup_group, registration=registration, created_by=created_by_user
    )
    SignUpContactPersonFactory(signup_group=signup_group)

    second_signup = SignUpFactory(registration=registration, created_by=created_by_user)
    SignUpContactPersonFactory(signup=second_signup)

    SignUpGroupProtectedDataFactory(
        signup_group=signup_group, registration=registration
    )
    SignUpProtectedDataFactory(signup=first_signup, registration=registration)
    SignUpProtectedDataFactory(signup=second_signup, registration=registration)

    EventFactory(
        user_email=created_by_user.email,
        user_name="test",
        user_organization="test",
        user_consent=True,
        user_phone_number="123",
        created_by=created_by_user,
    )


def _assert_gdpr_delete(
    callback,
    start_user_count=1,
    start_group_count=1,
    start_signup_count=2,
    start_contact_person_count=2,
    end_user_count=0,
    end_group_count=0,
    end_signup_count=0,
    end_contact_person_count=0,
):
    assert User.objects.count() == start_user_count
    assert SignUpGroup.objects.count() == start_group_count
    assert SignUp.objects.count() == start_signup_count

    assert SignUpContactPerson.objects.count() == start_contact_person_count

    assert SignUpGroupProtectedData.objects.count() == start_group_count
    assert SignUpProtectedData.objects.count() == start_signup_count

    callback()

    assert User.objects.count() == end_user_count
    assert SignUpGroup.objects.count() == end_group_count
    assert SignUp.objects.count() == end_signup_count

    assert SignUpContactPerson.objects.count() == end_contact_person_count

    assert SignUpGroupProtectedData.objects.count() == start_group_count
    assert SignUpProtectedData.objects.count() == start_signup_count


# === tests ===


@pytest.mark.django_db
def test_authenticated_user_can_delete_own_data(
    api_client, settings, django_capture_on_commit_callbacks
):
    user = UserFactory()

    _create_default_data(user)
    event = user.events_event_created_by.first()

    def callback():
        with (
            requests_mock.Mocker() as req_mock,
            patch(
                "registrations.signals._recalculate_registration_capacities"
            ) as mocked_signup_post_delete,
        ):
            auth_header = get_api_token_for_user_with_scopes(
                user.uuid, [settings.GDPR_API_DELETE_SCOPE], req_mock
            )
            api_client.credentials(HTTP_AUTHORIZATION=auth_header)

            with django_capture_on_commit_callbacks(execute=True):
                response = _delete_gdpr_data(api_client, user.uuid)
            assert response.status_code == status.HTTP_204_NO_CONTENT

            assert mocked_signup_post_delete.called is True

    _assert_gdpr_delete(callback)

    event.refresh_from_db()
    assert event.user_name is None
    assert event.user_email is None
    assert event.user_phone_number is None
    assert event.user_organization is None


@pytest.mark.django_db
def test_authenticated_user_can_delete_own_data_event_user_details_not_nulled(
    api_client, settings, django_capture_on_commit_callbacks
):
    user = UserFactory()

    _create_default_data(user)
    event = user.events_event_created_by.first()
    event.user_email = "someotherguy@localhost"
    event.save()

    def callback():
        with (
            requests_mock.Mocker() as req_mock,
            patch(
                "registrations.signals._recalculate_registration_capacities"
            ) as mocked_signup_post_delete,
        ):
            auth_header = get_api_token_for_user_with_scopes(
                user.uuid, [settings.GDPR_API_DELETE_SCOPE], req_mock
            )
            api_client.credentials(HTTP_AUTHORIZATION=auth_header)

            with django_capture_on_commit_callbacks(execute=True):
                response = _delete_gdpr_data(api_client, user.uuid)
            assert response.status_code == status.HTTP_204_NO_CONTENT

            assert mocked_signup_post_delete.called is True

    _assert_gdpr_delete(callback)

    event.refresh_from_db()
    assert event.user_name == "test"
    assert event.user_email == "someotherguy@localhost"
    assert event.user_phone_number == "123"
    assert event.user_organization == "test"


@pytest.mark.django_db
def test_authenticated_user_cannot_delete_own_data_with_upcoming_signups_in_group(
    api_client, settings, django_capture_on_commit_callbacks
):
    user = UserFactory()

    upcoming_event = EventFactory(end_time=timezone.now() + timezone.timedelta(days=1))
    registration = RegistrationFactory(event=upcoming_event)

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)
    signup = SignUpFactory(signup_group=signup_group, created_by=user)
    SignUpGroupProtectedDataFactory(
        signup_group=signup_group, registration=registration
    )
    SignUpProtectedDataFactory(signup=signup, registration=registration)
    SignUpContactPersonFactory(signup_group=signup_group)

    def callback():
        with requests_mock.Mocker() as req_mock:
            auth_header = get_api_token_for_user_with_scopes(
                user.uuid, [settings.GDPR_API_DELETE_SCOPE], req_mock
            )
            api_client.credentials(HTTP_AUTHORIZATION=auth_header)

            with django_capture_on_commit_callbacks(execute=True):
                response = _delete_gdpr_data(api_client, user.uuid)
            assert response.status_code == status.HTTP_403_FORBIDDEN
            code = response.data["errors"][0]["code"]
            assert code == "UPCOMING_SIGNUPS"

    _assert_gdpr_delete(
        callback,
        start_user_count=1,
        start_group_count=1,
        start_signup_count=1,
        start_contact_person_count=1,
        end_user_count=1,
        end_group_count=1,
        end_signup_count=1,
        end_contact_person_count=1,
    )


@pytest.mark.django_db
def test_authenticated_user_cannot_delete_own_data_with_upcoming_signups(
    api_client, settings, django_capture_on_commit_callbacks
):
    user = UserFactory()

    upcoming_event = EventFactory(end_time=timezone.now() + timezone.timedelta(days=1))
    registration = RegistrationFactory(event=upcoming_event)

    signup = SignUpFactory(registration=registration, created_by=user)
    SignUpProtectedDataFactory(signup=signup, registration=registration)
    SignUpContactPersonFactory(signup=signup)

    def callback():
        with requests_mock.Mocker() as req_mock:
            auth_header = get_api_token_for_user_with_scopes(
                user.uuid, [settings.GDPR_API_DELETE_SCOPE], req_mock
            )
            api_client.credentials(HTTP_AUTHORIZATION=auth_header)

            with django_capture_on_commit_callbacks(execute=True):
                response = _delete_gdpr_data(api_client, user.uuid)
            assert response.status_code == status.HTTP_403_FORBIDDEN

            code = response.data["errors"][0]["code"]
            assert code == "UPCOMING_SIGNUPS"

    _assert_gdpr_delete(
        callback,
        start_user_count=1,
        start_group_count=0,
        start_signup_count=1,
        start_contact_person_count=1,
        end_user_count=1,
        end_group_count=0,
        end_signup_count=1,
        end_contact_person_count=1,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payment_status",
    [
        SignUpPayment.PaymentStatus.CANCELLED,
        SignUpPayment.PaymentStatus.CREATED,
        SignUpPayment.PaymentStatus.REFUNDED,
    ],
)
def test_authenticated_user_cannot_delete_own_data_with_ongoing_payments(
    api_client, settings, django_capture_on_commit_callbacks, payment_status
):
    user = UserFactory()

    event = EventFactory(end_time=timezone.now() - timezone.timedelta(days=31))
    registration = RegistrationFactory(event=event)
    signup = SignUpFactory(registration=registration, created_by=user)
    SignUpPaymentFactory(signup=signup, status=payment_status, created_by=user)
    SignUpProtectedDataFactory(signup=signup, registration=registration)
    SignUpContactPersonFactory(signup=signup)

    def callback():
        with requests_mock.Mocker() as req_mock:
            auth_header = get_api_token_for_user_with_scopes(
                user.uuid, [settings.GDPR_API_DELETE_SCOPE], req_mock
            )
            api_client.credentials(HTTP_AUTHORIZATION=auth_header)

            with django_capture_on_commit_callbacks(execute=True):
                response = _delete_gdpr_data(api_client, user.uuid)
            assert response.status_code == status.HTTP_403_FORBIDDEN

            code = response.data["errors"][0]["code"]
            assert code == "ONGOING_PAYMENTS"

    _assert_gdpr_delete(
        callback,
        start_user_count=1,
        start_group_count=0,
        start_signup_count=1,
        start_contact_person_count=1,
        end_user_count=1,
        end_group_count=0,
        end_signup_count=1,
        end_contact_person_count=1,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payment_status",
    [
        SignUpPayment.PaymentStatus.CANCELLED,
        SignUpPayment.PaymentStatus.CREATED,
        SignUpPayment.PaymentStatus.REFUNDED,
    ],
)
def test_authenticated_user_cannot_delete_own_data_with_ongoing_payments_in_signup_group(
    api_client, settings, django_capture_on_commit_callbacks, payment_status
):
    user = UserFactory()

    event = EventFactory(end_time=timezone.now() - timezone.timedelta(days=31))
    registration = RegistrationFactory(event=event)
    signup_group = SignUpGroupFactory(registration=registration)
    signup = SignUpFactory(
        registration=registration, signup_group=signup_group, created_by=user
    )
    SignUpPaymentFactory(signup_group=signup_group, signup=None, status=payment_status)
    SignUpGroupProtectedDataFactory(
        signup_group=signup_group, registration=registration
    )
    SignUpProtectedDataFactory(signup=signup, registration=registration)
    SignUpContactPersonFactory(signup=signup)
    SignUpContactPersonFactory(signup_group=signup_group)

    def callback():
        with requests_mock.Mocker() as req_mock:
            auth_header = get_api_token_for_user_with_scopes(
                user.uuid, [settings.GDPR_API_DELETE_SCOPE], req_mock
            )
            api_client.credentials(HTTP_AUTHORIZATION=auth_header)

            with django_capture_on_commit_callbacks(execute=True):
                response = _delete_gdpr_data(api_client, user.uuid)
            assert response.status_code == status.HTTP_403_FORBIDDEN

            code = response.data["errors"][0]["code"]
            assert code == "ONGOING_PAYMENTS"

    _assert_gdpr_delete(
        callback,
        start_user_count=1,
        start_group_count=1,
        start_signup_count=1,
        start_contact_person_count=2,
        end_user_count=1,
        end_group_count=1,
        end_signup_count=1,
        end_contact_person_count=2,
    )


@pytest.mark.django_db
def test_authenticated_user_cannot_delete_other_users_data(api_client, settings):
    user = UserFactory()
    other_user = UserFactory()

    _create_default_data(other_user)

    def callback():
        with requests_mock.Mocker() as req_mock:
            auth_header = get_api_token_for_user_with_scopes(
                user.uuid, [settings.GDPR_API_DELETE_SCOPE], req_mock
            )
            api_client.credentials(HTTP_AUTHORIZATION=auth_header)

            response = _delete_gdpr_data(api_client, other_user.uuid)
            assert response.status_code == status.HTTP_403_FORBIDDEN

    _assert_gdpr_delete(
        callback,
        start_user_count=2,
        start_group_count=1,
        start_signup_count=2,
        start_contact_person_count=2,
        end_user_count=2,
        end_group_count=1,
        end_signup_count=2,
        end_contact_person_count=2,
    )


@pytest.mark.django_db
def test_non_authenticated_user_cannot_delete_any_data(api_client, settings):
    user = UserFactory()

    _create_default_data(user)

    def callback():
        response = _delete_gdpr_data(api_client, user.uuid)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    _assert_gdpr_delete(
        callback,
        start_user_count=1,
        start_group_count=1,
        start_signup_count=2,
        start_contact_person_count=2,
        end_user_count=1,
        end_group_count=1,
        end_signup_count=2,
        end_contact_person_count=2,
    )
