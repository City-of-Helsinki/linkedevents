import pytest
from rest_framework import status

from events.models import Event
from events.tests.conftest import APIClient
from events.tests.test_event_get import get_list_and_assert_events
from events.tests.utils import versioned_reverse as reverse

# === util methods ===


def get_list(api_client, query_string=None):
    url = reverse("registration-list")

    if query_string:
        url = "%s?%s" % (url, query_string)

    return api_client.get(url)


def assert_registrations_in_response(registrations, response, query=""):
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


def get_detail(api_client, pk, query_string=None):
    detail_url = reverse("registration-detail", kwargs={"pk": pk})

    if query_string:
        detail_url = "%s?%s" % (detail_url, query_string)

    return api_client.get(detail_url)


# === tests ===


@pytest.mark.parametrize(
    "event_type",
    [Event.TypeId.GENERAL, Event.TypeId.COURSE, Event.TypeId.VOLUNTEERING],
)
@pytest.mark.django_db
def test_get_registration(api_client, event, event_type, registration):
    event.type_id = event_type
    event.save()

    response = get_detail(api_client, registration.id)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == registration.id


@pytest.mark.django_db
def test_get_deleted_registration(api_client, registration):
    registration.deleted = True
    registration.save()

    response = get_detail(api_client, registration.id)
    assert response.status_code == status.HTTP_404_NOT_FOUND

    response = get_detail(api_client, registration.id, query_string="show_deleted=true")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == registration.id


@pytest.mark.django_db
def test_registration_list(
    api_client, registration, registration2, registration3, registration4
):
    get_list_and_assert_registrations(
        api_client, "", (registration, registration2, registration3, registration4)
    )


@pytest.mark.django_db
def test_registration_list_show_deleted_filter(
    api_client, registration, registration2, registration3, registration4
):
    registration.deleted = True
    registration.save()

    get_list_and_assert_registrations(
        api_client, "", (registration2, registration3, registration4)
    )
    get_list_and_assert_registrations(
        api_client,
        "show_deleted=true",
        (registration, registration2, registration3, registration4),
    )


@pytest.mark.django_db
def test_registration_list_admin_user_filter(
    api_client, registration, registration2, registration3, user
):
    api_client.force_authenticate(user)

    get_list_and_assert_registrations(
        api_client, "", (registration, registration2, registration3)
    )
    get_list_and_assert_registrations(
        api_client, "admin_user=true", (registration, registration3)
    )


@pytest.mark.django_db
def test_registration_list_event_type_filter(
    api_client, event, event2, event3, registration, registration2, registration3
):
    event.type_id = Event.TypeId.GENERAL
    event.save()
    event2.type_id = Event.TypeId.COURSE
    event2.save()
    event3.type_id = Event.TypeId.VOLUNTEERING
    event3.save()

    get_list_and_assert_registrations(
        api_client, "", (registration, registration2, registration3)
    )
    get_list_and_assert_registrations(api_client, "event_type=general", (registration,))
    get_list_and_assert_registrations(api_client, "event_type=course", (registration2,))
    get_list_and_assert_registrations(
        api_client, "event_type=volunteering", (registration3,)
    )


@pytest.mark.django_db
def test_filter_events_with_registrations(api_client, event, event2, registration):
    get_list_and_assert_events("", (event, event2), api_client)
    get_list_and_assert_events("registration=true", (event,), api_client)
    get_list_and_assert_events("registration=false", (event2,), api_client)
