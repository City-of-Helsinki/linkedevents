from datetime import datetime

import pytz
from django.conf import settings
from rest_framework.reverse import reverse
from rest_framework.settings import api_settings
from rest_framework.test import APIRequestFactory

from events.models import Event, EventAggregate, EventAggregateMember
from events.tests.factories import EventFactory


def assert_event_data_is_equal(d1, d2, version="v1"):
    # TODO: start using version parameter
    # make sure the saved data is equal to the one we posted before
    fields = (
        "data_source",
        "publisher",
        "location",
        "name_en",
        "event_status",
        "sub_events",
        "custom_data",
        "audience",
        "location_extra_info",
        "info_url",
        "description",
        "short_description",
        "provider",
        "keywords",
        "offers",
        "in_language",
        "external_links",
        "videos",
        "start_time",
        "end_time",
    )
    if version == "v1":
        fields += ("images",)
    elif version == "v0.1":
        fields += (
            "image",
            "headline",
            "secondary_headline",
            "origin_id",
        )
    assert_data_is_equal(d1, d2, fields)


def assert_place_data_is_equal(d1, d2, version="v1"):
    fields = (
        "data_source",
        "publisher",
        "email",
        "postal_code",
        "name",
        "description",
        "street_address",
        "address_locality",
        "position",
    )
    assert_data_is_equal(d1, d2, fields)


def assert_keyword_data_is_equal(d1, d2, version="v1"):
    fields = ("data_source", "publisher", "name")
    assert_data_is_equal(d1, d2, fields)


def assert_keyword_set_data_is_equal(d1, d2):
    fields = ("data_source", "organization", "name")
    assert_data_is_equal(d1, d2, fields)


def assert_data_is_equal(d1, d2, fields):
    for key in fields:
        if key in d1:
            if type(d1[key]) is list:
                assert_lists_match(d1[key], d2[key])
            else:
                assert d1[key] == d2[key], key


def get(api_client, url, data=None):
    response = api_client.get(url, data=data, format="json")
    assert response.status_code == 200, str(response.content)
    return response


def assert_lists_match(l1, l2):
    """
    Checks that l1 and l2 contain objects with all common fields identical
    :param l1: list with minimal objects
    :param l2: list with potentially extended objects
    :return:
    """
    assert len(l1) == len(l2)
    for object1 in l1:
        if type(object1) is dict:
            assert_list_contains_matching_dictionary(l2, object1)
        else:
            assert object1 in l2


def assert_list_contains_matching_dictionary(l1, dictionary):
    """
    Checks that l1 contains a dictionary with all the key-value pairs of given dictionary
    :param l1:
    :param dictionary:
    :return:
    """
    for object1 in l1:
        for key, value in dictionary.items():
            if object1[key] == value:
                continue
            else:
                # no match here
                break
        else:
            # required fields matched!
            return
    raise AssertionError


def assert_fields_exist(data, fields):
    for field in fields:
        assert field in data, "{} not found in {}".format(field, data)
    assert len(data) == len(fields)


def versioned_reverse(view, version="v1", **kwargs):
    factory = APIRequestFactory()
    request = factory.options("/")
    request.versioning_scheme = api_settings.DEFAULT_VERSIONING_CLASS()
    request.version = version
    return reverse(view, request=request, **kwargs)


def post_event(api_client, event_data):
    url = reverse("event-list", kwargs={"version": "v1"})
    response = api_client.post(url, event_data, format="json")
    assert response.status_code == 201, "{} {}".format(
        response.status_code, response.data
    )
    return response


def put_event(api_client, event, event_data):
    url = reverse("event-detail", kwargs={"version": "v1", "pk": event.pk})
    response = api_client.put(url, event_data, format="json")
    assert response.status_code == 200, "{} {}".format(
        response.status_code, response.data
    )
    return response


def datetime_zone_aware(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute).astimezone(
        pytz.timezone(settings.TIME_ZONE)
    )


def create_super_event(events: list[Event], data_source) -> Event:
    """Create super event for the given set of events."""
    aggregate = EventAggregate.objects.create()
    super_event = EventFactory(
        super_event_type=Event.SuperEventType.RECURRING,
        data_source=data_source,
        id="linkedevents:agg-{}".format(aggregate.id),
    )
    aggregate.super_event = super_event
    aggregate.save()
    event_aggregates = [
        EventAggregateMember(event=event, event_aggregate=aggregate) for event in events
    ]
    EventAggregateMember.objects.bulk_create(event_aggregates)
    for event in events:
        event.super_event = aggregate.super_event
    Event.objects.bulk_update(events, ("super_event",))
    return super_event
