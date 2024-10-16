from collections import Counter
from decimal import Decimal
from unittest.mock import PropertyMock, patch

import pytest
from django.conf import settings
from django.test import TestCase
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event
from events.tests.conftest import APIClient
from events.tests.factories import EventFactory
from events.tests.test_event_get import get_list_and_assert_events
from events.tests.utils import assert_fields_exist
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import PriceGroup, RegistrationPriceGroup, SignUp
from registrations.tests.factories import (
    PriceGroupFactory,
    RegistrationFactory,
    RegistrationUserAccessFactory,
    SeatReservationCodeFactory,
    SignUpFactory,
)
from registrations.tests.test_registration_post import hel_email
from registrations.tests.test_signup_post import assert_create_signups
from registrations.tests.utils import create_user_by_role

include_signups_query = "include=signups"
test_email = "test@email.com"


# === util methods ===


def get_list(api_client: APIClient, query_string: str = None):
    url = reverse("registration-list")

    if query_string:
        url = "%s?%s" % (url, query_string)

    return api_client.get(url)


def assert_registrations_in_response(
    registrations: list, response: dict, query: str = ""
):
    response_registration_ids = {event["id"] for event in response.data["data"]}
    expected_registration_ids = {registration.id for registration in registrations}
    if query:
        assert (
            response_registration_ids == expected_registration_ids
        ), f"\nquery: {query}"
    else:
        assert response_registration_ids == expected_registration_ids


def get_list_and_assert_registrations(
    api_client: APIClient, query: str, registrations: list
):
    response = get_list(api_client, query_string=query)
    assert_registrations_in_response(registrations, response, query)


def get_detail(api_client: APIClient, pk: str, query: str = None):
    detail_url = reverse("registration-detail", kwargs={"pk": pk})

    if query:
        detail_url = "%s?%s" % (detail_url, query)

    return api_client.get(detail_url)


def get_detail_and_assert_registration(
    api_client: APIClient, pk: str, query: str = None
):
    response = get_detail(api_client, pk, query)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == pk

    return response


def assert_registration_fields_exist(data, is_admin_user=False):
    fields = (
        "id",
        "signups",
        "current_attendee_count",
        "current_waiting_list_count",
        "remaining_attendee_capacity",
        "remaining_waiting_list_capacity",
        "data_source",
        "publisher",
        "has_registration_user_access",
        "has_substitute_user_access",
        "created_time",
        "last_modified_time",
        "event",
        "attendee_registration",
        "audience_min_age",
        "audience_max_age",
        "enrolment_start_time",
        "enrolment_end_time",
        "maximum_attendee_capacity",
        "minimum_attendee_capacity",
        "waiting_list_capacity",
        "maximum_group_size",
        "mandatory_fields",
        "confirmation_message",
        "instructions",
        "is_created_by_current_user",
        "signup_url",
        "registration_price_groups",
        "registration_merchant",
        "registration_account",
        "@id",
        "@context",
        "@type",
    )
    if is_admin_user:
        fields += (
            "created_by",
            "last_modified_by",
            "registration_user_accesses",
        )
    assert_fields_exist(data, fields)


# === tests ===


@pytest.mark.parametrize(
    "event_type",
    [Event.TypeId.GENERAL, Event.TypeId.COURSE, Event.TypeId.VOLUNTEERING],
)
@pytest.mark.django_db
def test_admin_can_get_registration_created_by_self(
    user_api_client, organization, user, event_type
):
    event = EventFactory(type_id=event_type, publisher=organization)
    registration = RegistrationFactory(event=event, created_by=user)

    assert registration.created_by_id == user.id

    response = get_detail_and_assert_registration(user_api_client, registration.id)
    assert response.data["is_created_by_current_user"] is True
    assert_registration_fields_exist(response.data, is_admin_user=True)


@pytest.mark.parametrize(
    "event_type",
    [Event.TypeId.GENERAL, Event.TypeId.COURSE, Event.TypeId.VOLUNTEERING],
)
@pytest.mark.django_db
def test_admin_can_get_registration_not_created_by_self(
    user_api_client, organization, user, user2, event_type
):
    event = EventFactory(type_id=event_type, publisher=organization)
    registration = RegistrationFactory(event=event, created_by=user2)

    assert registration.created_by_id != user.id

    response = get_detail_and_assert_registration(user_api_client, registration.id)
    assert response.data["is_created_by_current_user"] is False
    assert_registration_fields_exist(response.data, is_admin_user=True)


@pytest.mark.parametrize("user_role", ["admin", "registration_admin"])
@pytest.mark.django_db
def test_admin_or_registration_admin_can_see_registration_user_accesses(
    registration, api_client, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(registration=registration)
    RegistrationUserAccessFactory(registration=registration, email=test_email)

    response = get_detail_and_assert_registration(api_client, registration.id)
    response_registration_user_accesses = response.data["registration_user_accesses"]
    assert len(response_registration_user_accesses) == 2
    assert_registration_fields_exist(response.data, is_admin_user=True)


@pytest.mark.django_db
def test_registration_price_groups_in_response(registration, api_client):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(publisher=None).first()
    custom_price_group = PriceGroupFactory(
        publisher=registration.publisher,
        description_en="EN desc",
        description_fi="FI desc",
        description_sv="SV desc",
    )

    price_group1 = RegistrationPriceGroup.objects.create(
        registration=registration, price_group=default_price_group, price=Decimal("10")
    )
    price_group2 = RegistrationPriceGroup.objects.create(
        registration=registration, price_group=custom_price_group, price=Decimal("10")
    )

    response = get_detail_and_assert_registration(api_client, registration.id)
    assert len(response.data["registration_price_groups"]) == 2
    assert Counter(
        [data["id"] for data in response.data["registration_price_groups"]]
    ) == Counter([price_group1.pk, price_group2.pk])
    assert_fields_exist(
        response.data["registration_price_groups"][0],
        (
            "id",
            "price_group",
            "price",
            "vat_percentage",
            "price_without_vat",
            "vat",
        ),
    )

    price_group_fields = ("id", "description")
    language_fields = ("fi", "sv", "en")
    for index in range(2):
        assert_fields_exist(
            response.data["registration_price_groups"][index]["price_group"],
            price_group_fields,
        )
        assert_fields_exist(
            response.data["registration_price_groups"][index]["price_group"][
                "description"
            ],
            language_fields,
        )


@pytest.mark.django_db
def test_registration_user_access_user_can_see_if_he_has_access(
    registration, api_client
):
    user = create_user_by_role("regular_user", registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
    )

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        response = get_detail_and_assert_registration(api_client, registration.id)
        assert mocked.called is True

    assert response.data["has_registration_user_access"] is True
    assert response.data["has_substitute_user_access"] is False
    assert_registration_fields_exist(response.data, is_admin_user=False)


@pytest.mark.django_db
def test_registration_substitute_user_can_see_if_he_has_access(
    registration, api_client
):
    user = UserFactory(email=hel_email)
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=True,
    )

    response = get_detail_and_assert_registration(api_client, registration.id)

    assert response.data["has_registration_user_access"] is True
    assert response.data["has_substitute_user_access"] is True
    assert_registration_fields_exist(response.data, is_admin_user=True)


@pytest.mark.parametrize("user_role", ["financial_admin", "regular_user"])
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_see_registration_user_accesses(
    registration, api_client, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(registration=registration, email=user.email)
    response = get_detail_and_assert_registration(api_client, registration.id)

    assert response.data.get("registration_user_accesses") is None


@pytest.mark.django_db
def test_anonymous_user_can_see_registration(api_client, registration):
    response = get_detail(api_client, registration.id)

    assert response.status_code == status.HTTP_200_OK
    assert_registration_fields_exist(response.data, is_admin_user=False)


@pytest.mark.django_db
def test_get_registration_contains_correct_signup_url(user_api_client, registration):
    response = get_detail_and_assert_registration(user_api_client, registration.id)
    assert response.data["signup_url"] == {
        lang: f"{settings.LINKED_REGISTRATIONS_UI_URL}/{lang}/registration/{registration.id}/signup-group/create"
        for lang in ["en", "fi", "sv"]
    }


@pytest.mark.django_db
def test_get_registration_with_event_included(user_api_client, event, registration):
    response = get_detail_and_assert_registration(
        user_api_client, registration.id, "include=event"
    )
    response_event = response.data["event"]
    assert response_event["id"] == event.id
    assert list(response_event["name"].values())[0] == event.name
    assert list(response_event["description"].values())[0] == event.description
    assert response_event["publisher"] == event.publisher.id


@pytest.mark.django_db
def test_get_registration_with_event_and_location_included(
    user_api_client, event, place, registration
):
    event.location = place
    event.save()

    response = get_detail_and_assert_registration(
        user_api_client, registration.id, "include=event,location"
    )
    response_location = response.data["event"]["location"]
    assert response_location["id"] == place.id
    assert list(response_location["name"].values())[0] == place.name


@pytest.mark.django_db
def test_get_registration_with_event_and_keywords_included(
    user_api_client, event, keyword, registration
):
    event.keywords.add(keyword)
    event.save()

    response = get_detail_and_assert_registration(
        user_api_client, registration.id, "include=event,keywords"
    )
    response_keyword = response.data["event"]["keywords"][0]
    assert response_keyword["id"] == keyword.id
    assert list(response_keyword["name"].values())[0] == keyword.name


@pytest.mark.django_db
def test_get_registration_with_event_and_in_language_included(
    user_api_client, event, languages, registration
):
    language = languages[0]
    event.in_language.add(language)
    event.save()

    response = get_detail_and_assert_registration(
        user_api_client, registration.id, "include=event,in_language"
    )
    response_language = response.data["event"]["in_language"][0]
    assert response_language["id"] == language.id


@pytest.mark.django_db
def test_get_registration_with_event_and_audience_included(
    user_api_client, event, keyword, registration
):
    event.audience.add(keyword)
    event.save()

    response = get_detail_and_assert_registration(
        user_api_client, registration.id, "include=event,audience"
    )
    response_audience = response.data["event"]["audience"][0]
    assert response_audience["id"] == keyword.id
    assert list(response_audience["name"].values())[0] == keyword.name


@pytest.mark.django_db
def test_registration_created_admin_can_include_signups(
    registration, signup, signup2, user, user_api_client
):
    registration.created_by = user
    registration.save(update_fields=["created_by"])

    response = get_detail_and_assert_registration(
        user_api_client, registration.id, include_signups_query
    )
    assert len(response.data["signups"]) == 2


@pytest.mark.parametrize("is_substitute_user", [False, True])
@pytest.mark.django_db
def test_registration_user_access_can_include_signups_when_strongly_identified(
    registration, signup, signup2, api_client, is_substitute_user
):
    user = UserFactory(email=hel_email if is_substitute_user else "test@test.com")
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=is_substitute_user,
    )

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        response = get_detail_and_assert_registration(
            api_client, registration.id, include_signups_query
        )
        assert mocked.called is True

    response_signups = response.data["signups"]
    assert len(response_signups) == 2


@pytest.mark.django_db
def test_registration_user_access_cannot_include_signups_when_not_strongly_identified(
    registration, signup, signup2, api_client
):
    user = UserFactory()
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = get_detail_and_assert_registration(
            api_client, registration.id, include_signups_query
        )
        assert mocked.called is True

    response_signups = response.data["signups"]
    assert response_signups is None


@pytest.mark.django_db
def test_registration_substitute_user_can_include_signups_when_not_strongly_identified(
    registration, signup, signup2, api_client
):
    user = UserFactory(email=hel_email)
    user.organization_memberships.add(registration.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=True,
    )

    response = get_detail_and_assert_registration(
        api_client, registration.id, include_signups_query
    )
    response_signups = response.data["signups"]
    assert len(response_signups) == 2


@pytest.mark.parametrize("user_role", ["admin", "financial_admin", "regular_user"])
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_include_signups(
    registration, signup, signup2, api_client, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    if user_role == "admin":
        registration.created_by = UserFactory()
        registration.save(update_fields=["created_by"])

    response = get_detail_and_assert_registration(
        api_client, registration.id, include_signups_query
    )
    assert response.data["signups"] is None


@pytest.mark.django_db
def test_contact_person_cannot_include_signups(
    api_client, registration, signup, signup2
):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup.contact_person.user = user
    signup.contact_person.save(update_fields=["user"])
    signup2.contact_person.user = user
    signup2.contact_person.save(update_fields=["user"])

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        response = get_detail_and_assert_registration(
            api_client, registration.id, include_signups_query
        )
        assert mocked.called is True

    response_signups = response.data["signups"]
    assert response_signups is None


@pytest.mark.django_db
def test_current_attendee_and_waitlist_count(user_api_client):
    registration = RegistrationFactory(
        maximum_attendee_capacity=1, waiting_list_capacity=1
    )

    response = get_detail(user_api_client, registration.id)
    assert response.data["current_attendee_count"] == 0
    assert response.data["current_waiting_list_count"] == 0

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "first_name": "Michael",
        "last_name": "Jackson",
        "email": "test@test.com",
        "phone_number": "0441111111",
        "notifications": "sms",
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }
    assert_create_signups(user_api_client, signups_data)

    response = get_detail(user_api_client, registration.id)
    assert response.data["current_attendee_count"] == 1
    assert response.data["current_waiting_list_count"] == 0

    reservation2 = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data2 = {
        "first_name": "Michael",
        "last_name": "Jackson 2",
        "email": "test2@test.com",
        "phone_number": "20441111111",
        "notifications": "sms",
    }
    signups_data2 = {
        "registration": registration.id,
        "reservation_code": reservation2.code,
        "signups": [signup_data2],
    }
    assert_create_signups(user_api_client, signups_data2)

    response = get_detail(user_api_client, registration.id)
    assert response.data["current_attendee_count"] == 1
    assert response.data["current_waiting_list_count"] == 1


@pytest.mark.django_db
def test_registration_list(
    user_api_client, registration, registration2, registration3, registration4
):
    get_list_and_assert_registrations(
        user_api_client, "", [registration, registration2, registration3, registration4]
    )


@pytest.mark.django_db
def test_registration_list_admin_user_filter(
    organization3, registration, registration2, registration3, user, user_api_client
):
    registration3.event.publisher = organization3
    registration3.event.save()

    get_list_and_assert_registrations(
        user_api_client, "", [registration, registration2, registration3]
    )
    get_list_and_assert_registrations(
        user_api_client, "admin_user=true", [registration]
    )

    organization3.registration_admin_users.add(user)
    get_list_and_assert_registrations(
        user_api_client, "admin_user=true", [registration, registration3]
    )


@pytest.mark.django_db
def test_registration_list_substitute_user_filter(
    organization3, registration, registration2, registration3, api_client
):
    user = create_user_by_role("regular_user", registration.publisher)
    user.email = hel_email
    user.save(update_fields=["email"])
    api_client.force_authenticate(user)

    registration3.event.publisher = organization3
    registration3.event.save(update_fields=["publisher"])

    RegistrationUserAccessFactory(
        registration=registration,
        email=hel_email,
        is_substitute_user=True,
    )
    get_list_and_assert_registrations(
        api_client, "", [registration, registration2, registration3]
    )
    get_list_and_assert_registrations(api_client, "admin_user=true", [registration])

    RegistrationUserAccessFactory(
        registration=registration3,
        email=hel_email,
        is_substitute_user=True,
    )
    get_list_and_assert_registrations(
        api_client, "admin_user=true", [registration, registration3]
    )


@pytest.mark.django_db
def test_registration_list_event_type_filter(
    user_api_client, event, event2, event3, registration, registration2, registration3
):
    event.type_id = Event.TypeId.GENERAL
    event.save()
    event2.type_id = Event.TypeId.COURSE
    event2.save()
    event3.type_id = Event.TypeId.VOLUNTEERING
    event3.save()

    get_list_and_assert_registrations(
        user_api_client, "", [registration, registration2, registration3]
    )
    get_list_and_assert_registrations(
        user_api_client, "event_type=general", [registration]
    )
    get_list_and_assert_registrations(
        user_api_client, "event_type=course", [registration2]
    )
    get_list_and_assert_registrations(
        user_api_client, "event_type=volunteering", [registration3]
    )


@pytest.mark.django_db
def test_filter_events_with_registrations(api_client, event, event2, registration):
    get_list_and_assert_events("", (event, event2), api_client)
    get_list_and_assert_events("registration=true", (event,), api_client)
    get_list_and_assert_events("registration=false", (event2,), api_client)


@pytest.mark.django_db
def test_registration_id_is_audit_logged_on_get_detail(user_api_client, registration):
    response = get_detail(user_api_client, registration.id)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        registration.pk
    ]


@pytest.mark.django_db
def test_registration_id_is_audit_logged_on_get_list(
    user_api_client, registration, registration2
):
    response = get_list(user_api_client)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter([registration.pk, registration2.pk])


class RegistrationCapacityTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with cls.captureOnCommitCallbacks(execute=True):
            cls.registration = RegistrationFactory(
                maximum_attendee_capacity=5,
                waiting_list_capacity=5,
            )

        cls.registration_detail_url = reverse(
            "registration-detail", kwargs={"pk": cls.registration.pk}
        )

    def test_update_registration_maximum_attendee_capacity(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.registration.maximum_attendee_capacity = 4
            self.registration.save(update_fields=["maximum_attendee_capacity"])
        self.assertEqual(len(callbacks), 1)

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 4)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 5)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.registration.maximum_attendee_capacity = 5
            self.registration.save()
        self.assertEqual(len(callbacks), 1)

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 5)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 5)

    def test_update_registration_waiting_list_capacity(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.registration.waiting_list_capacity = 4
            self.registration.save(update_fields=["waiting_list_capacity"])
        self.assertEqual(len(callbacks), 1)

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 5)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 4)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.registration.waiting_list_capacity = 5
            self.registration.save()
        self.assertEqual(len(callbacks), 1)

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 5)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 5)

    def test_update_registration_both_capacities(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.registration.maximum_attendee_capacity = 4
            self.registration.waiting_list_capacity = 3
            self.registration.save(
                update_fields=["maximum_attendee_capacity", "waiting_list_capacity"]
            )
        self.assertEqual(len(callbacks), 1)

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 4)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 3)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.registration.maximum_attendee_capacity = 5
            self.registration.waiting_list_capacity = 4
            self.registration.save()
        self.assertEqual(len(callbacks), 1)

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 5)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 4)

    def test_update_non_capacity_field(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.registration.audience_min_age = 18
            self.registration.save(update_fields=["audience_min_age"])
        self.assertEqual(len(callbacks), 0)

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 5)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 5)

    def test_get_registration_remaining_attendee_capacity_is_none(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.registration.maximum_attendee_capacity = None
            self.registration.save(update_fields=["maximum_attendee_capacity"])
        self.assertEqual(len(callbacks), 1)

        response = self.client.get(self.registration_detail_url)
        self.assertIsNone(response.data["remaining_attendee_capacity"])
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 5)

    def test_get_registration_remaining_waiting_list_capacity_is_none(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.registration.waiting_list_capacity = None
            self.registration.save(update_fields=["waiting_list_capacity"])
        self.assertEqual(len(callbacks), 1)

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 5)
        self.assertIsNone(response.data["remaining_waiting_list_capacity"])

    def test_get_registration_with_attending_signup(self):
        with self.captureOnCommitCallbacks(execute=True):
            signup = SignUpFactory(
                registration=self.registration,
                attendee_status=SignUp.AttendeeStatus.ATTENDING,
            )

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 4)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 5)

        # Release reserved attendee capacity.
        with self.captureOnCommitCallbacks(execute=True):
            signup._individually_deleted = True
            signup.delete()

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 5)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 5)

    def test_get_registration_with_waitlisted_signup(self):
        with self.captureOnCommitCallbacks(execute=True):
            signup = SignUpFactory(
                registration=self.registration,
                attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
            )

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 5)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 4)

        # Release reserved waiting list capacity.
        with self.captureOnCommitCallbacks(execute=True):
            signup._individually_deleted = True
            signup.delete()

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 5)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 5)

    def test_get_registration_with_seat_reservations(self):
        with self.captureOnCommitCallbacks(execute=True):
            SeatReservationCodeFactory(registration=self.registration, seats=3)

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 2)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 5)

        with self.captureOnCommitCallbacks(execute=True):
            seat_reservation2 = SeatReservationCodeFactory(
                registration=self.registration, seats=3
            )

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 0)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 4)

        # Release the second reservation.
        with self.captureOnCommitCallbacks(execute=True):
            seat_reservation2.delete()

        response = self.client.get(self.registration_detail_url)
        self.assertEqual(response.data["remaining_attendee_capacity"], 2)
        self.assertEqual(response.data["remaining_waiting_list_capacity"], 5)
