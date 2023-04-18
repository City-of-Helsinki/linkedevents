import pytest
from rest_framework import status

from events.models import Event
from events.tests.conftest import APIClient
from events.tests.test_event_get import get_list_and_assert_events
from events.tests.utils import versioned_reverse as reverse

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


# === tests ===


@pytest.mark.parametrize(
    "event_type",
    [Event.TypeId.GENERAL, Event.TypeId.COURSE, Event.TypeId.VOLUNTEERING],
)
@pytest.mark.django_db
def test_get_registration(api_client, event, event_type, registration):
    event.type_id = event_type
    event.save()

    get_detail_and_assert_registration(api_client, registration.id)


@pytest.mark.django_db
def test_get_registration_with_event_included(api_client, event, registration):
    response = get_detail_and_assert_registration(
        api_client, registration.id, "include=event"
    )
    response_event = response.data["event"]
    assert response_event["id"] == event.id
    assert list(response_event["name"].values())[0] == event.name
    assert list(response_event["description"].values())[0] == event.description
    assert response_event["publisher"] == event.publisher.id


@pytest.mark.django_db
def test_get_registration_with_event_and_location_included(
    api_client, event, place, registration
):
    event.location = place
    event.save()

    response = get_detail_and_assert_registration(
        api_client, registration.id, "include=event,location"
    )
    response_location = response.data["event"]["location"]
    assert response_location["id"] == place.id
    assert list(response_location["name"].values())[0] == place.name


@pytest.mark.django_db
def test_get_registration_with_event_and_keywords_included(
    api_client, event, keyword, registration
):
    event.keywords.add(keyword)
    event.save()

    response = get_detail_and_assert_registration(
        api_client, registration.id, "include=event,keywords"
    )
    response_keyword = response.data["event"]["keywords"][0]
    assert response_keyword["id"] == keyword.id
    assert list(response_keyword["name"].values())[0] == keyword.name


@pytest.mark.django_db
def test_get_registration_with_event_and_in_language_included(
    api_client, event, languages, registration
):
    language = languages[0]
    event.in_language.add(language)
    event.save()

    response = get_detail_and_assert_registration(
        api_client, registration.id, "include=event,in_language"
    )
    response_language = response.data["event"]["in_language"][0]
    assert response_language["id"] == language.id


@pytest.mark.django_db
def test_get_registration_with_event_and_audience_included(
    api_client, event, keyword, registration
):
    event.audience.add(keyword)
    event.save()

    response = get_detail_and_assert_registration(
        api_client, registration.id, "include=event,audience"
    )
    response_audience = response.data["event"]["audience"][0]
    assert response_audience["id"] == keyword.id
    assert list(response_audience["name"].values())[0] == keyword.name


@pytest.mark.django_db
def test_registration_list(
    api_client, registration, registration2, registration3, registration4
):
    get_list_and_assert_registrations(
        api_client, "", (registration, registration2, registration3, registration4)
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
