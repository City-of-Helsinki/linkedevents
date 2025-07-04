from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from dateutil.parser import parse as dateutil_parse
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.auth import ApiKeyUser
from events.models import Event, Image, Keyword, Offer, Place
from events.tests.test_event_post import create_with_post
from events.tests.utils import assert_event_data_is_equal
from registrations.enums import VatPercentage
from registrations.models import OfferPriceGroup, PriceGroup
from registrations.tests.factories import OfferPriceGroupFactory, PriceGroupFactory

from ..api import ImageSerializer
from .factories import KeywordFactory, OfferFactory
from .utils import versioned_reverse as reverse

# === util methods ===


def update_with_put(api_client, event_id, event_data, credentials=None):
    if credentials:
        api_client.credentials(**credentials)
    response = api_client.put(event_id, event_data, format="json")
    return response


# === tests ===


@pytest.mark.django_db
def test__update_a_draft_with_put(api_client, minimal_event_dict, user):
    # create an event
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop("location")
    minimal_event_dict.pop("keywords")
    minimal_event_dict["publication_status"] = "draft"
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    data2 = response.data

    # store updates
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)

    # assert
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__cannot_update_a_draft_without_a_name(api_client, minimal_event_dict, user):
    # create an event
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop("location")
    minimal_event_dict.pop("keywords")
    minimal_event_dict["publication_status"] = "draft"
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    data2 = response.data

    # delete name
    data2["name"] = {"fi": None}
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)
    assert response2.status_code == 400
    assert "name" in response2.data
    data2.pop("name")
    response2 = update_with_put(api_client, event_id, data2)
    assert response2.status_code == 400
    assert "name" in response2.data


@pytest.mark.django_db
def test__cannot_update_an_event_without_a_short_description(
    api_client, minimal_event_dict, user
):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    data2 = response.data

    # delete name
    data2["short_description"] = {"fi": None}
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)
    assert response2.status_code == 400
    assert "short_description" in response2.data
    data2.pop("short_description")
    response2 = update_with_put(api_client, event_id, data2)
    assert response2.status_code == 400
    assert "short_description" in response2.data


@pytest.mark.django_db
def test__cannot_update_an_event_without_a_description(
    api_client, minimal_event_dict, user
):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    data2 = response.data

    # delete name
    data2["description"] = {"fi": None}
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)
    assert response2.status_code == 400
    assert "description" in response2.data
    data2.pop("description")
    response2 = update_with_put(api_client, event_id, data2)
    assert response2.status_code == 400
    assert "description" in response2.data


@pytest.mark.django_db
def test__keyword_n_events_updated(
    api_client, minimal_event_dict, user, data_source, organization, make_keyword_id
):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    call_command("update_n_events")
    assert Keyword.objects.get(id=data_source.id + ":test").n_events == 1
    data2 = response.data

    # change the keyword and add an audience
    event_id = data2.pop("@id")
    data2["keywords"] = [{"@id": make_keyword_id(data_source, organization, "test2")}]
    data2["audience"] = [{"@id": make_keyword_id(data_source, organization, "test3")}]
    update_with_put(api_client, event_id, data2)
    call_command("update_n_events")
    assert Keyword.objects.get(id=data_source.id + ":test").n_events == 0
    assert Keyword.objects.get(id=data_source.id + ":test2").n_events == 1
    assert Keyword.objects.get(id=data_source.id + ":test3").n_events == 1


@pytest.mark.django_db
def test__location_n_events_updated(
    api_client,
    minimal_event_dict,
    user,
    data_source,
    other_data_source,
    place2,
    make_location_id,
):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    call_command("update_n_events")
    assert Place.objects.get(id=data_source.id + ":test_location").n_events == 1
    data2 = response.data

    # change the location
    event_id = data2.pop("@id")
    data2["location"] = {"@id": make_location_id(place2)}
    update_with_put(api_client, event_id, data2)
    call_command("update_n_events")
    assert Place.objects.get(id=data_source.id + ":test_location").n_events == 0
    assert Place.objects.get(id=other_data_source.id + ":test_location_2").n_events == 1


@pytest.mark.freeze_time("2023-01-01")
@pytest.mark.django_db
def test__update_minimal_event_with_autopopulated_fields_with_put(
    api_client, minimal_event_dict, user, organization
):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    data = response.data

    assert_event_data_is_equal(minimal_event_dict, data)
    event_id = data["@id"]

    response2 = update_with_put(api_client, event_id, minimal_event_dict)
    assert_event_data_is_equal(data, response2.data)
    event = Event.objects.get(id=data["id"])
    assert event.created_by == user
    assert event.last_modified_by == user
    assert event.created_time is not None
    assert event.last_modified_time is not None
    assert event.data_source.id == settings.SYSTEM_DATA_SOURCE_ID
    assert event.publisher == organization
    # events are automatically marked as ending at midnight, local time
    assert event.end_time == timezone.localtime(
        timezone.now() + timedelta(days=2)
    ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(ZoneInfo("UTC"))
    assert event.has_end_time is False


@pytest.mark.xfail(reason="potential DST shenanigans")
@pytest.mark.freeze_time("2023-10-27")
@pytest.mark.django_db
def test__update_minimal_event_with_autopopulated_fields_with_put_dst(
    api_client, minimal_event_dict, user, organization
):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    data = response.data

    assert_event_data_is_equal(minimal_event_dict, data)
    event_id = data["@id"]

    response2 = update_with_put(api_client, event_id, minimal_event_dict)
    assert_event_data_is_equal(data, response2.data)
    event = Event.objects.get(id=data["id"])
    assert event.created_by == user
    assert event.last_modified_by == user
    assert event.created_time is not None
    assert event.last_modified_time is not None
    assert event.data_source.id == settings.SYSTEM_DATA_SOURCE_ID
    assert event.publisher == organization
    # events are automatically marked as ending at midnight, local time
    assert event.end_time == timezone.localtime(
        timezone.now() + timedelta(days=2)
    ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(ZoneInfo("UTC"))
    assert event.has_end_time is False


@pytest.mark.django_db
def test__update_an_event_complex_dict(api_client, complex_event_dict, user):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # dummy inputs
    text = "text updated"
    url = "http://localhost"

    # set up updates
    data2 = response.data

    for key in ("name",):
        for lang in ("fi", "en", "sv"):
            if lang in data2[key]:
                data2[key][lang] = "%s updated" % data2[key][lang]

    data2["type_id"] = "Volunteering"
    data2["offers"] = [
        {
            "is_free": False,
            "price": {"en": text, "sv": text, "fi": text},
            "description": {"en": text, "fi": text},
            "info_url": {"en": url, "sv": url, "fi": url},
        }
    ]
    data2["keywords"] = data2["keywords"][:1]
    data2["in_language"] = data2["in_language"][:2]

    # store updates
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)

    # assert
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__change_event_type(api_client, complex_event_dict, user):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    data2 = response.data
    data2["type_id"] = "Course"
    event_id = data2["@id"]
    response2 = update_with_put(api_client, event_id, data2)
    assert_event_data_is_equal(data2, response2.data)

    data2["type_id"] = "General"
    event_id = data2["@id"]
    response2 = update_with_put(api_client, event_id, data2)
    assert_event_data_is_equal(data2, response2.data)

    data2["type_id"] = "Non existing event type"
    event_id = data2["@id"]
    response2 = update_with_put(api_client, event_id, data2)
    assert str(response2.data["detail"]) == 'Invalid value "Non existing event type"'


@pytest.mark.django_db
def test__bulk_update_single_event(api_client, complex_event_dict, user):
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    data2 = response.data
    data2["type_id"] = "Volunteering"
    data3 = [data2]
    response2 = api_client.put("http://testserver/v1/event/", data3, format="json")
    assert_event_data_is_equal(data3, response2.data)

    data2["type_id"] = "Course"
    data3 = [data2]
    response2 = api_client.put("http://testserver/v1/event/", data3, format="json")
    assert_event_data_is_equal(data3, response2.data)


@pytest.mark.django_db
def test__update_an_event_with_naive_datetime(api_client, minimal_event_dict, user):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    data2 = response.data

    # store updates
    event_id = data2.pop("@id")
    data2["start_time"] = (datetime.now() + timedelta(days=1)).isoformat()
    response2 = update_with_put(api_client, event_id, data2)

    # API should have assumed UTC datetime
    data2["start_time"] = (
        timezone.make_aware(
            dateutil_parse(data2["start_time"]), timezone=ZoneInfo("UTC")
        )
        .isoformat()
        .replace("+00:00", "Z")
    )
    data2["event_status"] = "EventRescheduled"

    # last modified times cannot be equal as the event was updated
    data2.pop("last_modified_time")
    response2.data.pop("last_modified_time")
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__reschedule_an_event_with_put(api_client, complex_event_dict, user):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # create a new datetime
    new_datetime = (
        (timezone.now() + timedelta(days=3)).isoformat().replace("+00:00", "Z")
    )
    data2 = response.data
    data2["start_time"] = new_datetime
    data2["end_time"] = new_datetime

    # update the event
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend rescheduled the event
    data2["event_status"] = "EventRescheduled"
    assert_event_data_is_equal(data2, response2.data)

    # try to cancel marking as rescheduled
    data2["event_status"] = "EventScheduled"
    response3 = api_client.put(event_id, data2, format="json")

    # assert the event does not revert back to scheduled
    assert response3.status_code == 400
    assert "event_status" in response3.data

    # create a new datetime again
    new_datetime = (
        (timezone.now() + timedelta(days=3)).isoformat().replace("+00:00", "Z")
    )
    data2 = response2.data
    data2["start_time"] = new_datetime
    data2["end_time"] = new_datetime

    # update the event again
    response2 = update_with_put(api_client, event_id, data2)

    # assert the event remains rescheduled
    data2["event_status"] = "EventRescheduled"
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__postpone_an_event_with_put(api_client, complex_event_dict, user):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # remove the start_time
    data2 = response.data
    data2["start_time"] = None

    # postponing (like deleting) should be allowed even if event is incomplete (external events etc.)
    data2["keywords"] = []
    data2["location"] = None

    # update the event
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend postponed the event
    data2["event_status"] = "EventPostponed"
    assert_event_data_is_equal(data2, response2.data)

    # try to cancel marking as postponed, fill in missing data
    data2 = response2.data
    data2["keywords"] = complex_event_dict["keywords"]
    data2["location"] = complex_event_dict["location"]
    data2["event_status"] = "EventScheduled"
    response3 = api_client.put(event_id, data2, format="json")

    # assert the event does not revert back to scheduled
    assert response3.status_code == 400
    assert "event_status" in response2.data

    # reschedule and try to cancel marking
    new_datetime = (
        (timezone.now() + timedelta(days=3)).isoformat().replace("+00:00", "Z")
    )
    data2["start_time"] = new_datetime
    data2["end_time"] = new_datetime
    data2["event_status"] = "EventScheduled"
    response3 = api_client.put(event_id, data2, format="json")

    # assert the event does not revert back to scheduled
    assert response3.status_code == 400
    assert "event_status" in response3.data

    # reschedule, but do not try to cancel marking
    data2 = response2.data
    new_datetime = (
        (timezone.now() + timedelta(days=3)).isoformat().replace("+00:00", "Z")
    )
    data2["start_time"] = new_datetime
    data2["end_time"] = new_datetime
    data2.pop("event_status")
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)

    # assert the event is marked rescheduled
    data2["event_status"] = "EventRescheduled"
    assert_event_data_is_equal(data2, response2.data)

    # remove the start_time
    data2 = response2.data
    data2["start_time"] = None

    # update the event
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend postponed the event again
    data2["event_status"] = "EventPostponed"
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__cancel_an_event_with_put(api_client, complex_event_dict, user):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # mark the event cancelled
    data2 = response.data
    data2["event_status"] = "EventCancelled"

    # cancelling (like deleting) should be allowed even if event is incomplete (external events etc.)
    data2["keywords"] = []
    data2["location"] = None

    # update the event
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend cancelled the event
    data2["event_status"] = "EventCancelled"
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__cancel_a_postponed_event_with_put(api_client, complex_event_dict, user):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # remove the start_time
    data2 = response.data
    data2["start_time"] = None

    # update the event
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend postponed the event
    data2["event_status"] = "EventPostponed"
    assert_event_data_is_equal(data2, response2.data)

    # mark the event cancelled
    data2 = response.data
    data2["event_status"] = "EventCancelled"

    # update the event
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend cancelled the event
    data2["event_status"] = "EventCancelled"
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__cancel_a_rescheduled_event_with_put(api_client, complex_event_dict, user):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # create a new datetime
    new_datetime = (
        (timezone.now() + timedelta(days=3)).isoformat().replace("+00:00", "Z")
    )
    data2 = response.data
    data2["start_time"] = new_datetime
    data2["end_time"] = new_datetime

    # update the event
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend rescheduled the event
    data2["event_status"] = "EventRescheduled"
    assert_event_data_is_equal(data2, response2.data)

    # mark the event cancelled
    data2 = response.data
    data2["event_status"] = "EventCancelled"

    # update the event
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend cancelled the event
    data2["event_status"] = "EventCancelled"
    assert_event_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test__reschedule_a_cancelled_event_with_put(api_client, complex_event_dict, user):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)

    # mark the event cancelled
    data2 = response.data
    data2["event_status"] = "EventCancelled"

    # update the event
    event_id = data2.pop("@id")
    response2 = update_with_put(api_client, event_id, data2)

    # assert backend cancelled the event
    data2["event_status"] = "EventCancelled"
    assert_event_data_is_equal(data2, response2.data)

    # create a new datetime and remove the cancelled status
    new_datetime = (
        (timezone.now() + timedelta(days=3)).isoformat().replace("+00:00", "Z")
    )
    data3 = response2.data
    data3["start_time"] = new_datetime
    data3["end_time"] = new_datetime
    data3.pop("event_status")

    # update the event
    event_id = data3.pop("@id")
    response3 = update_with_put(api_client, event_id, data3)

    # assert backend rescheduled the event
    data3["event_status"] = "EventRescheduled"
    assert_event_data_is_equal(data3, response3.data)


# the following values may not be posted
@pytest.mark.django_db
@pytest.mark.parametrize(
    "non_permitted_input,non_permitted_response",
    [
        ({"id": "not_allowed:1"}, 400),  # may not fake id
        (
            {"id": settings.SYSTEM_DATA_SOURCE_ID + ":changed"},
            400,
        ),  # may not change object id
        ({"data_source": "theotherdatasourceid"}, 400),  # may not fake data source
        ({"publisher": "test_organization2"}, 400),  # may not fake organization
    ],
)
def test__non_editable_fields_at_put(
    api_client, minimal_event_dict, user, non_permitted_input, non_permitted_response
):
    # create the event first
    api_client.force_authenticate(user)
    response = create_with_post(api_client, minimal_event_dict)
    data2 = response.data
    event_id = data2.pop("@id")

    # try to put non permitted values
    data2.update(non_permitted_input)

    response2 = api_client.put(event_id, data2, format="json")
    assert response2.status_code == non_permitted_response
    if non_permitted_response >= 400:
        # check that there is an error message for the corresponding field
        assert list(non_permitted_input)[0] in response2.data


# the following values may not be posted
@pytest.mark.django_db
@pytest.mark.parametrize(
    "non_permitted_input,non_permitted_response",
    [
        ({"id": "not_allowed:1"}, 400),  # may not fake id
        (
            {"id": settings.SYSTEM_DATA_SOURCE_ID + ":changed"},
            400,
        ),  # may not change object id
        ({"data_source": "theotherdatasourceid"}, 400),  # may not fake data source
        ({"publisher": "test_organization2"}, 400),  # may not fake organization
    ],
)
def test__apikey_non_editable_fields_at_put(
    api_client,
    minimal_event_dict,
    organization,
    data_source,
    non_permitted_input,
    non_permitted_response,
):
    # create the event first
    data_source.owner = organization
    data_source.save()
    response = create_with_post(api_client, minimal_event_dict, data_source)
    data2 = response.data
    event_id = data2.pop("@id")

    # try to put non permitted values
    data2.update(non_permitted_input)

    response2 = api_client.put(
        event_id, data2, format="json", credentials={"apikey": data_source.api_key}
    )
    assert response2.status_code == non_permitted_response
    if non_permitted_response >= 400:
        # check that there is an error message for the corresponding field
        assert list(non_permitted_input)[0] in response2.data


@pytest.mark.django_db
def test__an_admin_can_update_an_event_from_another_data_source(
    api_client, event2, keyword, offer, other_data_source, organization, user
):
    other_data_source.owner = organization
    other_data_source.user_editable_resources = True
    other_data_source.save()
    event2.publisher = organization
    event2.keywords.add(
        keyword
    )  # keyword is needed in testing POST and PUT with event data
    event2.offers.add(offer)  # ditto for offer
    event2.maximum_attendee_capacity = 1000000
    event2.save()
    api_client.force_authenticate(user)

    detail_url = reverse("event-detail", kwargs={"pk": event2.pk})
    response = api_client.get(detail_url, format="json")
    assert response.status_code == 200
    response = update_with_put(api_client, detail_url, response.data)
    assert response.status_code == 200


@pytest.mark.django_db
def test__apikey_cannot_update_an_event_from_another_data_source(
    api_client, event2, keyword, offer, data_source, other_data_source, organization
):
    other_data_source.owner = organization
    other_data_source.save()
    event2.publisher = organization
    event2.keywords.add(
        keyword
    )  # keyword is needed in testing POST and PUT with event data
    event2.offers.add(offer)  # ditto for offer
    event2.save()

    detail_url = reverse("event-detail", kwargs={"pk": event2.pk})
    response = api_client.get(detail_url, format="json")
    assert response.status_code == 200
    response = update_with_put(
        api_client,
        detail_url,
        response.data,
        credentials={"apikey": data_source.api_key},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test__correct_api_key_can_update_an_event(
    api_client, event, complex_event_dict, data_source, organization
):
    data_source.owner = organization
    data_source.save()

    detail_url = reverse("event-detail", kwargs={"pk": event.pk})
    response = update_with_put(
        api_client,
        detail_url,
        complex_event_dict,
        credentials={"apikey": data_source.api_key},
    )
    assert response.status_code == 200
    assert ApiKeyUser.objects.all().count() == 1


@pytest.mark.django_db
def test__correct_api_key_can_update_an_event_in_suborganization(
    api_client,
    event2,
    complex_event_dict,
    other_data_source,
    organization,
    organization2,
):
    other_data_source.owner = organization
    other_data_source.save()

    organization2.parent = organization
    organization2.save()
    del complex_event_dict["publisher"]
    del complex_event_dict["data_source"]

    detail_url = reverse("event-detail", kwargs={"pk": event2.pk})
    response = update_with_put(
        api_client,
        detail_url,
        complex_event_dict,
        credentials={"apikey": other_data_source.api_key},
    )
    assert response.status_code == 200, response.data
    assert ApiKeyUser.objects.all().count() == 1


@pytest.mark.django_db
def test__correct_api_key_cannot_update_an_event_in_superorganization(
    api_client,
    event,
    complex_event_dict,
    other_data_source,
    organization,
    organization2,
):
    other_data_source.owner = organization2
    other_data_source.save()

    organization2.parent = organization
    organization2.save()
    del complex_event_dict["publisher"]
    del complex_event_dict["data_source"]

    detail_url = reverse("event-detail", kwargs={"pk": event.pk})
    response = update_with_put(
        api_client,
        detail_url,
        complex_event_dict,
        credentials={"apikey": other_data_source.api_key},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test__wrong_api_key_cannot_update_an_event(
    api_client,
    event,
    complex_event_dict,
    data_source,
    other_data_source,
    organization,
    organization2,
):
    data_source.owner = organization
    data_source.save()
    other_data_source.owner = organization2
    other_data_source.save()
    del complex_event_dict["publisher"]

    detail_url = reverse("event-detail", kwargs={"pk": event.pk})
    response = update_with_put(
        api_client,
        detail_url,
        complex_event_dict,
        credentials={"apikey": other_data_source.api_key},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test__api_key_without_organization_cannot_update_an_event(
    api_client, event, complex_event_dict, data_source
):
    detail_url = reverse("event-detail", kwargs={"pk": event.pk})
    response = update_with_put(
        api_client,
        detail_url,
        complex_event_dict,
        credentials={"apikey": data_source.api_key},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test__unknown_api_key_cannot_update_an_event(api_client, event, complex_event_dict):
    detail_url = reverse("event-detail", kwargs={"pk": event.pk})
    response = update_with_put(
        api_client, detail_url, complex_event_dict, credentials={"apikey": "unknown"}
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test__empty_api_key_cannot_update_an_event(
    api_client,
    event,
    complex_event_dict,
):
    detail_url = reverse("event-detail", kwargs={"pk": event.pk})
    response = update_with_put(
        api_client, detail_url, complex_event_dict, credentials={"apikey": ""}
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_multiple_event_update(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)
    minimal_event_dict_2 = deepcopy(minimal_event_dict)
    minimal_event_dict_2["name"]["fi"] = "testing_2"

    # create events first
    resp = create_with_post(api_client, minimal_event_dict)
    minimal_event_dict["id"] = resp.data["id"]
    resp = create_with_post(api_client, minimal_event_dict_2)
    minimal_event_dict_2["id"] = resp.data["id"]

    minimal_event_dict["name"]["fi"] = "updated_name"
    minimal_event_dict_2["name"]["fi"] = "updated_name_2"

    response = api_client.put(
        reverse("event-list"), [minimal_event_dict, minimal_event_dict_2], format="json"
    )
    assert response.status_code == 200

    event_names = set(Event.objects.values_list("name_fi", flat=True))

    assert event_names == {"updated_name", "updated_name_2"}


@pytest.mark.django_db
def test_multiple_event_update_with_incorrect_json(
    api_client, minimal_event_dict, organization, data_source
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)
    response = api_client.put(reverse("event-list"), minimal_event_dict, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_multiple_event_update_missing_data_fails(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)
    minimal_event_dict_2 = deepcopy(minimal_event_dict)
    minimal_event_dict_2["name"]["fi"] = "testaus_2"

    # create events first
    resp = create_with_post(api_client, minimal_event_dict)
    minimal_event_dict["id"] = resp.data["id"]
    resp = create_with_post(api_client, minimal_event_dict_2)
    minimal_event_dict_2["id"] = resp.data["id"]

    minimal_event_dict["name"]["fi"] = "updated_name"
    minimal_event_dict_2.pop(
        "name"
    )  # name is required, so the event update event should fail

    response = api_client.put(
        reverse("event-list"), [minimal_event_dict, minimal_event_dict_2], format="json"
    )
    assert response.status_code == 400
    assert "name" in response.data[1]

    event_names = set(Event.objects.values_list("name_fi", flat=True))

    # verify that first event isn't updated either
    assert event_names == {"testaus", "testaus_2"}


@pytest.mark.django_db
def test_multiple_event_update_non_allowed_data_fails(
    api_client, minimal_event_dict, other_data_source, user
):
    api_client.force_authenticate(user)
    minimal_event_dict_2 = deepcopy(minimal_event_dict)
    minimal_event_dict_2["name"]["fi"] = "testaus_2"

    # create events first
    resp = create_with_post(api_client, minimal_event_dict)
    minimal_event_dict["id"] = resp.data["id"]
    resp = create_with_post(api_client, minimal_event_dict_2)
    minimal_event_dict_2["id"] = resp.data["id"]

    minimal_event_dict["name"]["fi"] = "updated_name"
    minimal_event_dict_2["data_source"] = (
        other_data_source.id
    )  # data source not allowed

    response = api_client.put(
        reverse("event-list"), [minimal_event_dict, minimal_event_dict_2], format="json"
    )

    assert response.status_code == 400
    assert "data_source" in response.data

    event_names = set(Event.objects.values_list("name_fi", flat=True))

    # verify that first event isn't updated either
    assert event_names == {"testaus", "testaus_2"}


@pytest.mark.django_db
def test_cannot_edit_events_in_the_past(api_client, event, minimal_event_dict, user):
    api_client.force_authenticate(user)

    event.start_time = timezone.now() - timedelta(days=2)
    event.end_time = timezone.now() - timedelta(days=1)
    event.save(update_fields=("start_time", "end_time"))

    response = api_client.put(
        reverse("event-detail", kwargs={"pk": event.id}),
        minimal_event_dict,
        format="json",
    )
    assert response.status_code == 403
    assert "Cannot edit a past event" in str(response.content)


@pytest.mark.django_db
def test_can_edit_events_in_the_past_with_past_events_allowed(
    api_client, event, minimal_event_dict, user, data_source
):
    api_client.force_authenticate(user)

    data_source.edit_past_events = True
    data_source.save()

    event.start_time = timezone.now() - timedelta(days=2)
    event.end_time = timezone.now() - timedelta(days=1)
    event.save(update_fields=("start_time", "end_time"))

    response = api_client.put(
        reverse("event-detail", kwargs={"pk": event.id}),
        minimal_event_dict,
        format="json",
    )
    assert response.status_code == 200
    assert_event_data_is_equal(minimal_event_dict, response.data)


@pytest.mark.django_db
def test_response_contains_replacing_event(api_client, event, minimal_event_dict, user):
    api_client.force_authenticate(user)

    response = create_with_post(api_client, minimal_event_dict)

    pk = response.data["id"]
    minimal_event_dict["replaced_by"] = event.pk
    response2 = api_client.put(
        reverse("event-detail", kwargs={"pk": pk}), minimal_event_dict, format="json"
    )
    assert response2.status_code == 200
    assert response2.data["id"] == event.pk


@pytest.mark.django_db
def test_update_draft_with_image_from_different_datasource(
    api_client,
    organization,
    data_source,
    organization2,
    other_data_source,
    minimal_event_dict,
    user,
):
    api_client.force_authenticate(user=user)

    minimal_event_dict.pop("location")
    minimal_event_dict.pop("keywords")
    minimal_event_dict["publication_status"] = "draft"
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)

    response_data = response.data
    event_id = response_data.pop("@id")
    image = Image.objects.create(
        name="image",
        data_source=other_data_source,
        publisher=organization,
        url="http://fake.url/image/",
    )

    image_url = reverse(ImageSerializer.view_name, kwargs={"pk": image.id})

    response_data["images"] = [{"@id": image_url}]

    response = update_with_put(api_client, event_id, response_data)

    assert response.status_code == 200, str(response.content)


@pytest.mark.django_db
def test_can_remove_deprecated_keyword(api_client, event, minimal_event_dict, user):
    api_client.force_authenticate(user)
    deprecated_kw = KeywordFactory(deprecated=True)
    event.keywords.add(deprecated_kw)

    response = api_client.put(
        reverse("event-detail", kwargs={"pk": event.id}),
        minimal_event_dict,
        format="json",
    )
    assert response.status_code == 200
    assert deprecated_kw not in event.keywords.all()


@pytest.mark.django_db
def test_event_id_is_audit_logged_on_put(user_api_client, minimal_event_dict):
    response = create_with_post(user_api_client, minimal_event_dict)
    event_id = response.data.pop("@id")

    update_with_put(user_api_client, event_id, minimal_event_dict)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data["id"]
    ]


@pytest.mark.django_db
def test_update_price_groups_to_event_offer(user_api_client, event, minimal_event_dict):
    OfferFactory(event=event)

    default_price_group = PriceGroup.objects.filter(publisher=None).first()
    custom_price_group = PriceGroupFactory(publisher=event.publisher)

    assert OfferPriceGroup.objects.count() == 0
    assert Offer.objects.count() == 1

    minimal_event_dict["offers"] = [
        {
            "is_free": False,
            "price": {"fi": "10 - 15.55 €"},
            "offer_price_groups": [
                {
                    "price_group": default_price_group.pk,
                    "price": Decimal("10"),
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                },
                {
                    "price_group": custom_price_group.pk,
                    "price": Decimal("15.55"),
                    "vat_percentage": VatPercentage.VAT_14.value,
                },
            ],
        }
    ]
    response = user_api_client.put(
        reverse("event-detail", kwargs={"pk": event.id}),
        minimal_event_dict,
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["offers"][0]["offer_price_groups"]) == 2

    assert OfferPriceGroup.objects.count() == 2
    assert Offer.objects.count() == 1

    offer = Offer.objects.filter(event=event).first()
    assert (
        OfferPriceGroup.objects.filter(
            offer=offer,
            price_group=default_price_group.pk,
            price=minimal_event_dict["offers"][0]["offer_price_groups"][0]["price"],
            vat_percentage=minimal_event_dict["offers"][0]["offer_price_groups"][0][
                "vat_percentage"
            ],
            price_without_vat=Decimal("7.97"),
            vat=Decimal("2.03"),
        ).count()
        == 1
    )
    assert (
        OfferPriceGroup.objects.filter(
            offer=offer,
            price_group=custom_price_group,
            price=minimal_event_dict["offers"][0]["offer_price_groups"][1]["price"],
            vat_percentage=minimal_event_dict["offers"][0]["offer_price_groups"][1][
                "vat_percentage"
            ],
            price_without_vat=Decimal("13.64"),
            vat=Decimal("1.91"),
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_update_existing_event_offer_price_group(
    user_api_client, event, minimal_event_dict
):
    default_price_group = PriceGroup.objects.filter(publisher=None).first()
    custom_price_group = PriceGroupFactory(publisher=event.publisher)

    offer = OfferFactory(event=event)
    offer_price_group = OfferPriceGroupFactory(
        offer=offer,
        price_group=default_price_group,
        price=Decimal("10"),
        vat_percentage=VatPercentage.VAT_25_5.value,
        price_without_vat=Decimal("7.97"),
        vat=Decimal("2.03"),
    )

    assert OfferPriceGroup.objects.count() == 1
    assert Offer.objects.count() == 1

    minimal_event_dict["offers"] = [
        {
            "is_free": False,
            "price": {"fi": "10 - 15.55 €"},
            "offer_price_groups": [
                {
                    "id": offer_price_group.pk,
                    "price_group": custom_price_group.pk,
                    "price": Decimal("5"),
                    "vat_percentage": VatPercentage.VAT_0.value,
                },
            ],
        }
    ]
    response = user_api_client.put(
        reverse("event-detail", kwargs={"pk": event.id}),
        minimal_event_dict,
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["offers"][0]["offer_price_groups"]) == 1
    assert (
        response.data["offers"][0]["offer_price_groups"][0]["id"]
        == offer_price_group.pk
    )

    assert OfferPriceGroup.objects.count() == 1
    assert Offer.objects.count() == 1

    offer = Offer.objects.filter(event=event).first()
    assert (
        OfferPriceGroup.objects.filter(
            offer=offer,
            price_group=custom_price_group,
            price=minimal_event_dict["offers"][0]["offer_price_groups"][0]["price"],
            vat_percentage=minimal_event_dict["offers"][0]["offer_price_groups"][0][
                "vat_percentage"
            ],
            price_without_vat=Decimal("5"),
            vat=Decimal("0"),
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_update_event_offer_price_groups_excluded_is_deleted(
    user_api_client, event, minimal_event_dict
):
    default_price_group = PriceGroup.objects.filter(publisher=None).first()
    custom_price_group = PriceGroupFactory(publisher=event.publisher)

    offer = OfferFactory(event=event)
    offer_price_group = OfferPriceGroupFactory(
        offer=offer,
        price_group=default_price_group,
        price=Decimal("10"),
        vat_percentage=VatPercentage.VAT_25_5.value,
        price_without_vat=Decimal("7.97"),
        vat=Decimal("2.03"),
    )

    assert OfferPriceGroup.objects.count() == 1
    assert Offer.objects.count() == 1

    minimal_event_dict["offers"] = [
        {
            "is_free": False,
            "price": {"fi": "10 - 15.55 €"},
            "offer_price_groups": [
                {
                    "price_group": custom_price_group.pk,
                    "price": Decimal("5"),
                    "vat_percentage": VatPercentage.VAT_0.value,
                },
            ],
        }
    ]
    response = user_api_client.put(
        reverse("event-detail", kwargs={"pk": event.id}),
        minimal_event_dict,
        format="json",
    )
    assert len(response.data["offers"][0]["offer_price_groups"]) == 1
    assert (
        response.data["offers"][0]["offer_price_groups"][0]["id"]
        != offer_price_group.pk
    )

    assert OfferPriceGroup.objects.count() == 1
    assert Offer.objects.count() == 1

    offer = Offer.objects.filter(event=event).first()
    assert (
        OfferPriceGroup.objects.filter(
            offer=offer,
            price_group=custom_price_group,
            price=minimal_event_dict["offers"][0]["offer_price_groups"][0]["price"],
            vat_percentage=minimal_event_dict["offers"][0]["offer_price_groups"][0][
                "vat_percentage"
            ],
            price_without_vat=Decimal("5"),
            vat=Decimal("0"),
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_cannot_update_event_offer_with_duplicate_price_groups(
    user_api_client, event, minimal_event_dict
):
    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    offer = OfferFactory(event=event)
    registration_price_group = OfferPriceGroupFactory(
        offer=offer,
        price_group=default_price_group,
    )

    assert OfferPriceGroup.objects.count() == 1

    minimal_event_dict["offers"] = [
        {
            "is_free": False,
            "price": {"fi": "10 - 15.55 €"},
            "offer_price_groups": [
                {
                    "id": registration_price_group.pk,
                    "price_group": default_price_group.pk,
                    "price": Decimal("5"),
                    "vat_percentage": VatPercentage.VAT_0.value,
                },
                {
                    "price_group": default_price_group.pk,
                    "price": Decimal("5"),
                    "vat_percentage": VatPercentage.VAT_0.value,
                },
            ],
        }
    ]
    response = user_api_client.put(
        reverse("event-detail", kwargs={"pk": event.id}),
        minimal_event_dict,
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["offers"][0]["offer_price_groups"][1]["price_group"][0] == (
        f"Offer price group with price_group {default_price_group} already exists."
    )

    assert OfferPriceGroup.objects.count() == 1


@pytest.mark.django_db
def test_update_event_with_large_minimum_and_maximum_attendee_capacity(
    user_api_client,
    event,
    minimal_event_dict,
):
    minimal_event_dict["minimum_attendee_capacity"] = 500000
    minimal_event_dict["maximum_attendee_capacity"] = 1000000

    response = user_api_client.put(
        reverse("event-detail", kwargs={"pk": event.id}),
        minimal_event_dict,
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK

    event.refresh_from_db()
    assert event.minimum_attendee_capacity == 500000
    assert event.maximum_attendee_capacity == 1000000


@pytest.mark.django_db
def test_update_event_external_link_texts_are_cleaned(
    user_api_client, event, minimal_event_dict
):
    cleaned_name = "&lt;p&gt;Test&lt;/p&gt;"
    link = "https://example.com"
    language = "fi"

    minimal_event_dict["external_links"] = [
        {
            "name": "<p>Test</p>",
            "link": link,
            "language": language,
        }
    ]

    response = user_api_client.put(
        reverse("event-detail", kwargs={"pk": event.id}),
        minimal_event_dict,
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["external_links"][0] == {
        "name": cleaned_name,
        "link": link,
        "language": language,
    }

    event.refresh_from_db()
    assert event.external_links.count() == 1

    external_link = event.external_links.first()
    assert external_link.name == cleaned_name
    assert external_link.link == link
    assert external_link.language_id == language


@pytest.mark.django_db
def test_update_event_duplicate_external_links_are_not_allowed(
    user_api_client, event, minimal_event_dict
):
    name = "Test"
    link = "https://example.com"
    language = "fi"

    minimal_event_dict["external_links"] = [
        {"name": name, "link": link, "language": language} for _ in range(2)
    ]

    response = user_api_client.put(
        reverse("event-detail", kwargs={"pk": event.id}),
        minimal_event_dict,
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["external_links"]["name"]
        == f"Duplicate link given with name {name}."
    )
    assert response.data["external_links"]["language"] == (
        f"Duplicate link given with language {language}."
    )
    assert (
        response.data["external_links"]["link"]
        == f"Duplicate link given with link {link}."
    )

    event.refresh_from_db()
    assert event.external_links.count() == 0
