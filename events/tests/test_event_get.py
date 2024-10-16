from collections import Counter
from datetime import datetime, timedelta

import pytest
import pytz
from dateutil import parser
from django.conf import settings
from django.contrib.gis.gdal import CoordTransform, SpatialReference
from django.contrib.gis.geos import Point
from django.db import DEFAULT_DB_ALIAS, connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils.timezone import localtime
from freezegun import freeze_time
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event, Language, PublicationStatus
from events.tests.conftest import APIClient
from events.tests.factories import EventFactory, OfferFactory
from events.tests.utils import assert_fields_exist, datetime_zone_aware, get
from events.tests.utils import versioned_reverse as reverse
from registrations.tests.factories import OfferPriceGroupFactory, RegistrationFactory

api_client = APIClient()


# === util methods ===
def get_list(api_client, version="v1", data=None, query_string=None):
    url = reverse("event-list", version=version)
    if query_string:
        url = "%s?%s" % (url, query_string)
    return get(api_client, url, data=data)


def get_list_no_code_assert(api_client, version="v1", data=None, query_string=None):
    url = reverse("event-list", version=version)
    if query_string:
        url = "%s?%s" % (url, query_string)
    return api_client.get(url, data=data, format="json")


def get_detail(api_client, detail_pk, version="v1", data=None):
    detail_url = reverse("event-detail", version=version, kwargs={"pk": detail_pk})
    return get(api_client, detail_url, data=data)


def assert_event_fields_exist(data, version="v1"):
    # TODO: incorporate version parameter into version aware
    # parts of test code
    fields = (
        "@context",
        "@id",
        "@type",
        "audience",
        "created_time",
        "custom_data",
        "data_source",
        "date_published",
        "description",
        "end_time",
        "event_status",
        "external_links",
        "id",
        "images",
        "in_language",
        "info_url",
        "has_user_editable_resources",
        "keywords",
        "last_modified_time",
        "location",
        "location_extra_info",
        "name",
        "offers",
        "provider",
        "provider_contact_info",
        "publisher",
        "short_description",
        "audience_min_age",
        "audience_max_age",
        "start_time",
        "sub_events",
        "super_event",
        "super_event_type",
        "videos",
        "replaced_by",
        "deleted",
        "local",
        "type_id",
        "enrolment_start_time",
        "maximum_attendee_capacity",
        "minimum_attendee_capacity",
        "enrolment_end_time",
        "registration",
        "environment",
        "environmental_certificate",
    )
    if version == "v0.1":
        fields += (
            "origin_id",
            "headline",
            "secondary_headline",
        )
    assert_fields_exist(data, fields)


def assert_offer_fields_exist(data):
    fields = (
        "description",
        "info_url",
        "is_free",
        "offer_price_groups",
        "price",
    )
    assert_fields_exist(data, fields)


def assert_offer_price_group_fields_exist(data):
    fields = (
        "id",
        "price_group",
        "price",
        "vat_percentage",
        "price_without_vat",
        "vat",
    )
    assert_fields_exist(data, fields)


def assert_events_in_response(events, response, query=""):
    response_event_ids = {event["id"] for event in response.data["data"]}
    expected_event_ids = {event.id for event in events}
    if query:
        assert response_event_ids == expected_event_ids, f"\nquery: {query}"
    else:
        assert response_event_ids == expected_event_ids


def get_list_and_assert_events(
    query: str, events: list, api_client: APIClient = api_client
):
    response = get_list(api_client, query_string=query)
    assert_events_in_response(events, response, query)


def get_detail_and_assert_events(
    query: str, events: list, api_client: APIClient = api_client
):
    response = get(api_client, query_string=query)
    assert_events_in_response(events, response, query)


# === tests ===


class EventsListTestCaseMixin:
    def _assert_events_in_response(self, events, response):
        response_event_ids = [event["id"] for event in response.data["data"]]
        expected_event_ids = [event.id for event in events]
        self.assertTrue(Counter(response_event_ids) == Counter(expected_event_ids))

    def _get_list_and_assert_events(self, query_string=None, events=None):
        if query_string:
            url = "%s?%s" % (self.list_url, query_string)
        else:
            url = self.list_url

        response = self.client.get(url)
        self._assert_events_in_response(events or [], response)


@pytest.mark.django_db
def test_get_event_list_html_renders(api_client, event):
    url = reverse("event-list", version="v1")
    response = api_client.get(
        url,
        data=None,
        headers={"accept": "text/html"},
    )
    assert response.status_code == status.HTTP_200_OK, str(response.content)


@pytest.mark.django_db
def test_get_event_list_check_fields_exist(api_client, event):
    """
    Tests that event list endpoint returns the correct fields.
    """
    response = get_list(api_client)
    assert_event_fields_exist(response.data["data"][0])


@pytest.mark.django_db
def test_get_event_detail_check_fields_exist(api_client, event):
    """
    Tests that event detail endpoint returns the correct fields.
    """
    response = get_detail(api_client, event.pk)
    assert_event_fields_exist(response.data)


@pytest.mark.django_db
def test_get_event_list_returns_events_from_cache_with_local_ongoing_or_set(
    django_cache, api_client
):
    event1 = EventFactory()
    event2 = EventFactory()
    EventFactory.create_batch(10)
    django_cache.set("local_ids", {event1.id: "keyword", event2.id: "avainsana"})

    get_list_and_assert_events("local_ongoing_OR_set1=keyword", [event1])


@pytest.mark.django_db
def test_get_event_list_returns_events_from_cache_with_internet_ongoing_or_set(
    django_cache, api_client
):
    event1 = EventFactory()
    event2 = EventFactory()
    EventFactory.create_batch(10)
    django_cache.set("internet_ids", {event1.id: "keyword", event2.id: "avainsana"})

    get_list_and_assert_events("internet_ongoing_OR_set1=keyword", [event1])


@pytest.mark.django_db
def test_get_event_list_returns_events_from_cache_with_all_ongoing_or_set(
    django_cache, api_client
):
    event1 = EventFactory()
    event2 = EventFactory()
    event3 = EventFactory()
    event4 = EventFactory()
    EventFactory.create_batch(10)
    django_cache.set("local_ids", {event1.id: "keyword", event2.id: "avainsana"})
    django_cache.set("internet_ids", {event3.id: "keyword", event4.id: "avainsana"})

    get_list_and_assert_events("all_ongoing_OR_set1=keyword", [event1, event3])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    [
        "local_ongoing_OR_set1=xxxxxxxxx",
        "all_ongoing_OR_set1=xxxxxxxxx",
        "internet_ongoing_OR_set1=xxxxxxxxx",
    ],
)
def test_get_event_list_returns_empty_list_on_invalid_ongoing_or_set_value(
    django_cache, api_client, query
):
    event1 = EventFactory()
    event2 = EventFactory()
    EventFactory.create_batch(10)
    django_cache.set("local_ids", {event1.id: "keyword", event2.id: "keyword2"})
    django_cache.set("internet_ids", {event1.id: "keyword", event2.id: "keyword2"})

    get_list_and_assert_events(query, [])


@pytest.mark.django_db
def test_get_unknown_event_detail_check_404(api_client):
    response = api_client.get(reverse("event-detail", kwargs={"pk": "möö"}))
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_get_event_list_verify_text_filter(api_client, event, event2):
    # Search with event name
    get_list_and_assert_events(f"text={event.name}", [event])
    # Search with place name
    get_list_and_assert_events(f"text={event.location.name}", [event])


@pytest.mark.django_db
def test_get_event_list_verify_data_source_filter(
    api_client, data_source, event, event2
):
    get_list_and_assert_events(f"data_source={data_source.id}", [event])


@pytest.mark.django_db
def test_get_event_list_verify_data_source_negative_filter(
    api_client, data_source, event, event2
):
    get_list_and_assert_events(f"data_source!={data_source.id}", [event2])


@pytest.mark.django_db
def test_get_event_list_verify_location_filter(api_client, place, event, event2):
    get_list_and_assert_events(f"location={place.id}", [event])


@pytest.mark.django_db
def test_get_event_list_verify_bbox_filter(api_client, event, event2):
    # API parameters must be provided in EPSG:4326 instead of the database SRS
    left_bottom = Point(25, 25)
    right_top = Point(75, 75)
    ct = CoordTransform(
        SpatialReference(settings.PROJECTION_SRID),
        SpatialReference(settings.WGS84_SRID),
    )
    left_bottom.transform(ct)
    right_top.transform(ct)
    get_list_and_assert_events(
        f"bbox={left_bottom.x},{left_bottom.y},{right_top.x},{right_top.y}", [event]
    )


@pytest.mark.django_db
def test_get_event_list_verify_dwithin_filter(event, event2):
    def with_default_srid(query):
        return f"srid={settings.PROJECTION_SRID}&{query}"

    origin = Point(24, 24)
    assert origin.distance(event.location.position) > 36
    assert origin.distance(event2.location.position) < 34

    # Don't filter if missing either origin or metres.
    get_list_and_assert_events(f"dwithin_origin={origin.x},{origin.y}", [event, event2])
    get_list_and_assert_events("dwithin_metres=35", [event, event2])

    get_list_and_assert_events(
        with_default_srid(f"dwithin_origin={origin.x},{origin.y}&dwithin_metres=35"),
        [event2],
    )
    get_list_and_assert_events(
        with_default_srid(f"dwithin_origin={origin.x},{origin.y}&dwithin_metres=37"),
        [event, event2],
    )

    # Should work with a float distance as well.
    get_list_and_assert_events(
        with_default_srid(f"dwithin_origin={origin.x},{origin.y}&dwithin_metres=35.01"),
        [event2],
    )


@pytest.mark.django_db
def test_get_event_list_returns_400_when_invalid_srid(event):
    origin = Point(24, 24)

    query_string = f"srid=777&dwithin_origin={origin.x},{origin.y}"
    url = reverse("event-list") + "?%s" % query_string

    response = api_client.get(url, format="json")

    assert response.status_code == 400


@pytest.mark.parametrize(
    "query_string,expected_message",
    [
        ("dwithin_origin=0,0&dwithin_metres=foo", "Metres must be a number"),
        ("dwithin_origin=0&dwithin_metres=35", "Origin must be a tuple of two numbers"),
        (
            "dwithin_origin=0,0,0&dwithin_metres=35",
            "Origin must be a tuple of two numbers",
        ),
        (
            "dwithin_origin=0,foo&dwithin_metres=35",
            "Origin must be a tuple of two numbers",
        ),
    ],
)
@pytest.mark.django_db
def test_get_event_list_verify_dwithin_filter_error(
    query_string, expected_message, api_client, event, event2
):
    response = get_list_no_code_assert(api_client, query_string=query_string)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == expected_message


@pytest.mark.django_db
def test_get_event_list_verify_audience_max_age_lt_filter(api_client, keyword, event):
    event.audience_max_age = 16
    event.save()
    get_list_and_assert_events(f"audience_max_age_lt={event.audience_max_age}", [event])
    get_list_and_assert_events(f"audience_max_age_lt={event.audience_max_age - 1}", [])
    get_list_and_assert_events(
        f"audience_max_age_lt={event.audience_max_age + 1}", [event]
    )


@pytest.mark.django_db
def test_get_event_list_verify_audience_max_age_gt_filter(api_client, keyword, event):
    #  'audience_max_age' parameter is identical to audience_max_age_gt and is kept for compatibility's sake
    event.audience_max_age = 16
    event.save()
    get_list_and_assert_events(f"audience_max_age_gt={event.audience_max_age}", [event])
    get_list_and_assert_events(
        f"audience_max_age_gt={event.audience_max_age - 1}", [event]
    )
    get_list_and_assert_events(f"audience_max_age_gt={event.audience_max_age + 1}", [])
    get_list_and_assert_events(f"audience_max_age={event.audience_max_age}", [event])
    get_list_and_assert_events(
        f"audience_max_age={event.audience_max_age - 1}", [event]
    )
    get_list_and_assert_events(f"audience_max_age={event.audience_max_age + 1}", [])


@pytest.mark.django_db
def test_get_event_list_verify_audience_min_age_lt_filter(api_client, keyword, event):
    #  'audience_max_age' parameter is identical to audience_max_age_gt and is kept for compatibility's sake
    event.audience_min_age = 14
    event.save()
    get_list_and_assert_events(f"audience_min_age_lt={event.audience_min_age}", [event])
    get_list_and_assert_events(f"audience_min_age_lt={event.audience_min_age - 1}", [])
    get_list_and_assert_events(
        f"audience_min_age_lt={event.audience_min_age + 1}", [event]
    )

    #  'audience_max_age' parameter is identical to audience_max_age_lt and is kept for compatibility's sake
    get_list_and_assert_events(f"audience_min_age={event.audience_min_age}", [event])
    get_list_and_assert_events(f"audience_min_age={event.audience_min_age - 1}", [])
    get_list_and_assert_events(
        f"audience_min_age={event.audience_min_age + 1}", [event]
    )


@pytest.mark.django_db
def test_get_event_list_verify_audience_min_age_gt_filter(api_client, keyword, event):
    #  'audience_max_age' parameter is identical to audience_max_age_gt and is kept for compatibility's sake
    event.audience_min_age = 14
    event.save()
    get_list_and_assert_events(f"audience_min_age_gt={event.audience_min_age}", [event])
    get_list_and_assert_events(
        f"audience_min_age_gt={event.audience_min_age - 1}", [event]
    )
    get_list_and_assert_events(f"audience_min_age_gt={event.audience_min_age + 1}", [])


@pytest.mark.django_db
def test_get_event_list_start_hour_filter(api_client, keyword, event):
    event.start_time = datetime_zone_aware(2020, 1, 1, 16, 30)
    event.save()
    get_list_and_assert_events("starts_after=16", [event])
    get_list_and_assert_events("starts_after=16:", [event])
    get_list_and_assert_events("starts_after=15:59", [event])
    get_list_and_assert_events("starts_after=16:30", [event])
    get_list_and_assert_events("starts_after=17:30", [])

    response = get_list_no_code_assert(api_client, data={"starts_after": "27:30"})
    assert response.status_code == 400
    response = get_list_no_code_assert(api_client, data={"starts_after": "18:70"})
    assert response.status_code == 400
    response = get_list_no_code_assert(api_client, data={"starts_after": ":70"})
    assert response.status_code == 400
    response = get_list_no_code_assert(api_client, data={"starts_after": "18:70:"})
    assert response.status_code == 400

    get_list_and_assert_events("starts_before=16:30", [event])
    get_list_and_assert_events("starts_before=17:30", [event])
    get_list_and_assert_events("starts_before=16:29", [])


@pytest.mark.django_db
def test_get_event_list_end_hour_filter(api_client, keyword, event):
    event.start_time = datetime_zone_aware(2020, 1, 1, 13, 30)
    event.end_time = datetime_zone_aware(2020, 1, 1, 16, 30)
    event.save()
    get_list_and_assert_events("ends_after=16:30", [event])
    get_list_and_assert_events("ends_after=17:30", [])
    get_list_and_assert_events("ends_after=16:29", [event])

    get_list_and_assert_events("ends_before=16:30", [event])
    get_list_and_assert_events("ends_before=17:30", [event])
    get_list_and_assert_events("ends_before=16:29", [])


@pytest.mark.django_db
def test_get_event_list_verify_keyword_filter(api_client, keyword, event, event2):
    event.keywords.add(keyword)
    get_list_and_assert_events(f"keyword={keyword.id}", [event])


@pytest.mark.django_db
def test_get_event_list_verify_keyword_or_filter(api_client, keyword, event, event2):
    # "keyword_OR" filter should be the same as "keyword" filter
    event.keywords.add(keyword)
    get_list_and_assert_events(f"keyword_OR={keyword.id}", [event])


@pytest.mark.django_db
def test_get_event_list_verify_combine_keyword_and_keyword_or(
    api_client, keyword, keyword2, event, event2
):
    # If "keyword" and "keyword_OR" are both present "AND" them together
    event.keywords.add(keyword, keyword2)
    event2.keywords.add(keyword2)
    get_list_and_assert_events(
        f"keyword={keyword.id}&keyword_OR={keyword2.id}", [event]
    )


@pytest.mark.django_db
def test_get_event_list_verify_keyword_and(
    api_client, keyword, keyword2, event, event2
):
    event.keywords.add(keyword)
    event2.keywords.add(keyword, keyword2)
    get_list_and_assert_events(f"keyword_AND={keyword.id},{keyword2.id}", [event2])

    event2.keywords.remove(keyword2)
    event2.audience.add(keyword2)
    get_list_and_assert_events(f"keyword_AND={keyword.id},{keyword2.id}", [event2])


@pytest.mark.django_db
def test_get_event_list_verify_keyword_negative_filter(
    api_client, keyword, keyword2, event, event2
):
    event.keywords.set([keyword])
    event2.keywords.set([keyword2])
    get_list_and_assert_events(f"keyword!={keyword.id}", [event2])
    get_list_and_assert_events(f"keyword!={keyword.id},{keyword2.id}", [])

    event.keywords.set([])
    event.audience.set([keyword])
    get_list_and_assert_events(f"keyword!={keyword.id}", [event2])


@pytest.mark.django_db
def test_get_event_list_verify_replaced_keyword_filter(
    api_client, keyword, keyword2, event
):
    event.keywords.add(keyword2)
    keyword.replaced_by = keyword2
    keyword.deleted = True
    keyword.save()
    get_list_and_assert_events(f"keyword={keyword.id}", [event])
    get_list_and_assert_events("keyword=unknown_keyword", [])


@pytest.mark.django_db
def test_get_event_list_verify_division_filter(
    api_client, event, event2, event3, administrative_division, administrative_division2
):
    event.location.divisions.set([administrative_division])
    event2.location.divisions.set([administrative_division2])

    get_list_and_assert_events(f"division={administrative_division.ocd_id}", [event])
    get_list_and_assert_events(
        f"division={administrative_division.ocd_id},{administrative_division2.ocd_id}",
        [event, event2],
    )  # noqa E501


@pytest.mark.django_db
def test_get_event_list_super_event_filters(api_client, event, event2):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.save()

    get_list_and_assert_events("super_event=none", [event])
    get_list_and_assert_events(f"super_event={event.id}", [event2])


@pytest.mark.django_db
def test_get_event_list_recurring_filters(api_client, event, event2):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.save()

    get_list_and_assert_events("recurring=super", [event])
    get_list_and_assert_events("recurring=sub", [event2])


@pytest.mark.django_db
def test_super_event_type_filter(api_client, event, event2):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.save()

    # "none" and "null" should return only the non super event
    for value in ("none", "null"):
        get_list_and_assert_events(f"super_event_type={value}", [event2])

    # "recurring" should return only the recurring super event
    get_list_and_assert_events("super_event_type=recurring", [event])

    # "recurring,none" should return both
    get_list_and_assert_events("super_event_type=recurring,none", [event, event2])
    get_list_and_assert_events("super_event_type=fwfiuwhfiuwhiw", [])


@pytest.mark.django_db
def test_get_event_disallow_simultaneous_include_super_and_sub(
    api_client, event, event2
):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.save()

    # fetch event with super event
    detail_url = reverse("event-detail", version="v1", kwargs={"pk": event2.pk})

    # If not specifically handled, the following combination of
    # include parameters causes an infinite recursion, because the
    # super events of sub events of super events ... are expanded ad
    # infinitum. This test is here to check that execution finishes.
    detail_url += "?include=super_event,sub_events"
    response = get(api_client, detail_url)
    assert_event_fields_exist(response.data)
    assert type(response.data["super_event"] == "dict")


@pytest.mark.django_db
def test_language_filter(api_client, event, event2, event3):
    event.name_sv = "namn"
    event.save()
    event2.in_language.add(Language.objects.get_or_create(id="en")[0])
    event2.in_language.add(Language.objects.get_or_create(id="sv")[0])
    event2.save()
    event3.name_ru = "название"
    event3.in_language.add(Language.objects.get_or_create(id="et")[0])
    event3.save()

    # Finnish should be the default language
    get_list_and_assert_events("language=fi", [event, event2, event3])
    # in_language is explicit filter on the in_language field, so no results for fi
    get_list_and_assert_events("in_language=fi", [])

    # Swedish should have two events (matches in_language and name_sv)
    get_list_and_assert_events("language=sv", [event, event2])
    get_list_and_assert_events("in_language=sv", [event2])

    # English should have one event (matches in_language)
    get_list_and_assert_events("language=en", [event2])
    get_list_and_assert_events("in_language=en", [event2])

    # Russian should have one event (matches name_ru)
    get_list_and_assert_events("language=ru", [event3])
    get_list_and_assert_events("in_language=ru", [])

    # Chinese should have no events
    get_list_and_assert_events("language=zh_hans", [])
    get_list_and_assert_events("in_language=zh_hans", [])

    # Estonian should have one event (matches in_language), even without translations available
    get_list_and_assert_events("language=et", [event3])
    get_list_and_assert_events("in_language=et", [event3])


@pytest.mark.django_db
def test_event_list_filters(api_client, event, event2):
    filters = (
        ([event.publisher.id, event2.publisher.id], "publisher"),
        ([event.data_source.id, event2.data_source.id], "data_source"),
    )

    for filter_values, filter_name in filters:
        q = ",".join(filter_values)
        get_list_and_assert_events(f"{filter_name}={q}", [event, event2])


@pytest.mark.django_db
def test_event_list_publisher_ancestor_filter(
    api_client, event, event2, organization, organization2, organization3
):
    organization2.parent = organization
    organization2.save()
    event.publisher = organization2
    event.save()
    event2.publisher = organization3
    event2.save()
    get_list_and_assert_events(f"publisher_ancestor={organization.id}", [event])


@pytest.mark.django_db
def test_publication_status_filter(
    api_client, event, event2, user, organization, data_source
):
    event.publication_status = PublicationStatus.PUBLIC
    event.save()

    event2.publication_status = PublicationStatus.DRAFT
    event2.save()

    api_client.force_authenticate(user=user)
    get_list_and_assert_events(
        "show_all=true&publication_status=public", [event], api_client
    )

    # cannot see drafts from other organizations
    get_list_and_assert_events("show_all=true&publication_status=draft", [], api_client)

    event2.publisher = organization
    event2.data_source = data_source
    event2.save()
    get_list_and_assert_events(
        "show_all=true&publication_status=draft", [event2], api_client
    )


@pytest.mark.django_db
def test_event_status_filter(
    api_client, event, event2, event3, event4, user, organization, data_source
):
    event.event_status = Event.Status.SCHEDULED
    event.save()
    event2.event_status = Event.Status.RESCHEDULED
    event2.save()
    event3.event_status = Event.Status.CANCELLED
    event3.save()
    event4.event_status = Event.Status.POSTPONED
    event4.save()
    get_list_and_assert_events("event_status=eventscheduled", [event])
    get_list_and_assert_events("event_status=eventrescheduled", [event2])
    get_list_and_assert_events("event_status=eventcancelled", [event3])
    get_list_and_assert_events("event_status=eventpostponed", [event4])
    get_list_and_assert_events(
        "event_status=eventscheduled,eventpostponed",
        [event, event4],
    )
    get_list_and_assert_events(
        "event_status=eventscheduled,eventrescheduled,eventcancelled,eventpostponed",
        [event, event2, event3, event4],
    )


@pytest.mark.django_db
def test_admin_user_filter(api_client, event, event2, user):
    api_client.force_authenticate(user=user)
    get_list_and_assert_events("admin_user=true", [event], api_client)


@pytest.mark.django_db
def test_registration_admin_user_filter(
    event, event2, event3, organization3, user, user_api_client
):
    event3.publisher = organization3
    event3.save()
    event2.publisher.registration_admin_users.add(user)
    get_list_and_assert_events(
        "registration_admin_user=false", [event, event2, event3], user_api_client
    )
    event2.publisher.registration_admin_users.add(user)
    get_list_and_assert_events(
        "registration_admin_user=true", [event, event2], user_api_client
    )


@pytest.mark.django_db
def test_cannot_use_registration_admin_user_and_admin_user_filters_simultaneously(
    user_api_client,
):
    url = "%s?%s" % (
        reverse("event-list"),
        "admin_user=true&registration_admin_user=true",
    )
    response = api_client.get(url, format="json")
    assert (
        response.data["detail"]
        == "Supply either 'admin_user' or 'registration_admin_user', not both"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_redirect_if_replaced(api_client, event, event2, user):
    api_client.force_authenticate(user=user)

    event.replaced_by = event2
    event.save()

    url = reverse("event-detail", version="v1", kwargs={"pk": event.pk})
    response = api_client.get(url, format="json")
    assert response.status_code == status.HTTP_301_MOVED_PERMANENTLY

    response2 = api_client.get(response.url, format="json")
    assert response2.status_code == status.HTTP_200_OK
    assert response2.data["id"] == event2.pk


@pytest.mark.django_db
def test_redirect_to_end_of_replace_chain(api_client, event, event2, event3, user):
    api_client.force_authenticate(user=user)

    event.replaced_by = event2
    event.save()
    event2.replaced_by = event3
    event2.save()

    url = reverse("event-detail", version="v1", kwargs={"pk": event.pk})
    response = api_client.get(url, format="json")
    assert response.status_code == status.HTTP_301_MOVED_PERMANENTLY

    response2 = api_client.get(response.url, format="json")
    assert response2.status_code == status.HTTP_200_OK
    assert response2.data["id"] == event3.pk


@pytest.mark.django_db
def test_get_event_list_sub_events(api_client, event, event2):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.save()

    # fetch event with sub event
    detail_url = reverse("event-detail", version="v1", kwargs={"pk": event.pk})
    response = get(api_client, detail_url)
    assert_event_fields_exist(response.data)
    assert response.data["sub_events"]


@pytest.mark.django_db
def test_get_event_list_deleted_sub_events(api_client, event, event2):
    event.super_event_type = Event.SuperEventType.RECURRING
    event.save()
    event2.super_event = event
    event2.deleted = True
    event2.save()

    # fetch event with sub event deleted
    detail_url = reverse("event-detail", version="v1", kwargs={"pk": event.pk})
    response = get(api_client, detail_url)
    assert_event_fields_exist(response.data)
    assert not response.data["sub_events"]


@pytest.mark.django_db
def test_event_list_show_deleted_param(api_client, event, event2, user):
    api_client.force_authenticate(user=user)

    event.soft_delete()

    response = get_list(api_client, query_string="show_deleted=true")
    assert response.status_code == status.HTTP_200_OK
    assert event.id in {e["id"] for e in response.data["data"]}
    assert event2.id in {e["id"] for e in response.data["data"]}

    expected_keys = ["id", "name", "last_modified_time", "deleted", "replaced_by"]
    event_data = next((e for e in response.data["data"] if e["id"] == event.id))
    assert len(event_data) == len(expected_keys)
    for key in event_data:
        assert key in expected_keys
    assert event_data["name"]["fi"] == "POISTETTU"
    assert event_data["name"]["sv"] == "RADERAD"
    assert event_data["name"]["en"] == "DELETED"
    get_list_and_assert_events("", [event2], api_client)


@pytest.mark.django_db
def test_event_list_deleted_param(api_client, event, event2, user):
    api_client.force_authenticate(user=user)

    event.soft_delete()

    response = get_list(api_client, query_string="deleted=true")
    assert response.status_code == status.HTTP_200_OK
    assert event.id in {e["id"] for e in response.data["data"]}
    assert event2.id not in {e["id"] for e in response.data["data"]}

    expected_keys = ["id", "name", "last_modified_time", "deleted", "replaced_by"]
    event_data = next((e for e in response.data["data"] if e["id"] == event.id))
    assert len(event_data) == len(expected_keys)
    for key in event_data:
        assert key in expected_keys
    assert event_data["name"]["fi"] == "POISTETTU"
    assert event_data["name"]["sv"] == "RADERAD"
    assert event_data["name"]["en"] == "DELETED"
    get_list_and_assert_events("", [event2], api_client)


@pytest.mark.django_db
def test_event_list_is_free_filter(api_client, event, event2, event3, offer):
    get_list_and_assert_events("is_free=true", [event2])
    get_list_and_assert_events("is_free=false", [event, event3])


@pytest.mark.django_db
def test_start_end_iso_date(api_client, make_event):
    event1 = make_event(
        "1",
        parser.parse("2020-02-19 23:00:00+02"),
        parser.parse("2020-02-19 23:30:00+02"),
    )
    event2 = make_event(
        "2",
        parser.parse("2020-02-19 23:30:00+02"),
        parser.parse("2020-02-20 00:00:00+02"),
    )
    event3 = make_event(
        "3",
        parser.parse("2020-02-19 23:30:00+02"),
        parser.parse("2020-02-20 00:30:00+02"),
    )
    event4 = make_event(
        "4",
        parser.parse("2020-02-20 00:00:00+02"),
        parser.parse("2020-02-20 00:30:00+02"),
    )
    event5 = make_event(
        "5",
        parser.parse("2020-02-20 12:00:00+02"),
        parser.parse("2020-02-20 13:00:00+02"),
    )
    event6 = make_event(
        "6",
        parser.parse("2020-02-21 12:00:00+02"),
        parser.parse("2020-02-21 13:00:00+02"),
    )
    event7 = make_event("7")  # postponed event

    # Start parameter
    get_list_and_assert_events(
        "start=2020-02-19", [event1, event2, event3, event4, event5, event6, event7]
    )

    response = get_list(api_client, query_string="start=2020-02-20")
    expected_events = [event3, event4, event5, event6, event7]
    assert_events_in_response(expected_events, response)
    get_list_and_assert_events(
        "start=2020-02-20", [event3, event4, event5, event6, event7]
    )

    # End parameter
    get_list_and_assert_events("end=2020-02-19", [event1, event2, event3, event4])
    get_list_and_assert_events(
        "end=2020-02-20", [event1, event2, event3, event4, event5]
    )

    # Start and end parameters
    get_list_and_assert_events(
        "start=2020-02-20&end=2020-02-20", [event3, event4, event5]
    )
    get_list_and_assert_events(
        "start=2020-02-19&end=2020-02-21",
        [event1, event2, event3, event4, event5, event6],
    )


@pytest.mark.django_db
def test_start_end_iso_date_time(api_client, make_event):
    event1 = make_event(
        "1",
        parser.parse("2020-02-19 10:00:00+02"),
        parser.parse("2020-02-19 11:22:33+02"),
    )
    event2 = make_event(
        "2",
        parser.parse("2020-02-19 11:22:33+02"),
        parser.parse("2020-02-19 22:33:44+02"),
    )
    event3 = make_event(
        "3",
        parser.parse("2020-02-20 11:22:33+02"),
        parser.parse("2020-02-20 22:33:44+02"),
    )
    event4 = make_event("4")  # postponed event

    # Start parameter
    get_list_and_assert_events(
        "start=2020-02-19T11:22:32", [event1, event2, event3, event4]
    )
    get_list_and_assert_events("start=2020-02-19T11:22:33", [event2, event3, event4])

    # End parameter
    get_list_and_assert_events("end=2020-02-19T11:22:32", [event1])
    get_list_and_assert_events("end=2020-02-19T11:22:33", [event1, event2])

    # Start and end parameters
    get_list_and_assert_events(
        "start=2020-02-19T11:22:33&end=2020-02-19T11:22:33", [event2]
    )


@pytest.mark.django_db
def test_start_end_today(api_client, make_event):
    event1 = make_event(
        "1",
        parser.parse("2020-02-19 23:00:00+02"),
        parser.parse("2020-02-19 23:30:00+02"),
    )
    event2 = make_event(
        "2",
        parser.parse("2020-02-19 23:30:00+02"),
        parser.parse("2020-02-20 00:00:00+02"),
    )
    event3 = make_event(
        "3",
        parser.parse("2020-02-19 23:30:00+02"),
        parser.parse("2020-02-20 00:30:00+02"),
    )
    event4 = make_event(
        "4",
        parser.parse("2020-02-20 00:00:00+02"),
        parser.parse("2020-02-20 00:30:00+02"),
    )
    event5 = make_event(
        "5",
        parser.parse("2020-02-20 12:00:00+02"),
        parser.parse("2020-02-20 13:00:00+02"),
    )
    event6 = make_event(
        "6",
        parser.parse("2020-02-21 00:00:00+02"),
        parser.parse("2020-02-21 01:00:00+02"),
    )
    event7 = make_event(
        "7",
        parser.parse("2020-02-21 12:00:00+02"),
        parser.parse("2020-02-21 13:00:00+02"),
    )
    event8 = make_event("8")  # postponed event

    def times():
        yield "2020-02-20 00:00:00+02"
        yield "2020-02-20 12:00:00+02"
        yield "2020-02-20 23:59:59+02"

    # Start parameter
    with freeze_time(times):
        get_list_and_assert_events(
            "start=today", [event3, event4, event5, event6, event7, event8]
        )

    # End parameter
    with freeze_time(times):
        get_list_and_assert_events(
            "end=today", [event1, event2, event3, event4, event5, event6]
        )

    # Start and end parameters
    with freeze_time(times):
        get_list_and_assert_events(
            "start=today&end=today", [event3, event4, event5, event6]
        )


@pytest.mark.django_db
def test_start_end_now(api_client, make_event):
    event1 = make_event(
        "1",
        parser.parse("2020-02-19 23:00:00+02"),
        parser.parse("2020-02-19 23:30:00+02"),
    )
    event2 = make_event(
        "2",
        parser.parse("2020-02-19 23:30:00+02"),
        parser.parse("2020-02-20 00:00:00+02"),
    )
    event3 = make_event(
        "3",
        parser.parse("2020-02-19 23:30:00+02"),
        parser.parse("2020-02-20 00:30:00+02"),
    )
    event4 = make_event(
        "4",
        parser.parse("2020-02-20 00:00:00+02"),
        parser.parse("2020-02-20 00:30:00+02"),
    )
    event5 = make_event(
        "5",
        parser.parse("2020-02-20 12:00:00+02"),
        parser.parse("2020-02-20 13:00:00+02"),
    )
    event6 = make_event(
        "6",
        parser.parse("2020-02-21 00:00:00+02"),
        parser.parse("2020-02-21 01:00:00+02"),
    )
    event7 = make_event(
        "7",
        parser.parse("2020-02-21 12:00:00+02"),
        parser.parse("2020-02-21 13:00:00+02"),
    )
    event8 = make_event("8")  # postponed event

    # Start parameter
    with freeze_time("2020-02-20 00:30:00+02"):
        get_list_and_assert_events("start=now", [event5, event6, event7, event8])

    # End parameter
    with freeze_time("2020-02-20 12:00:00+02"):
        get_list_and_assert_events("end=now", [event1, event2, event3, event4, event5])

    # Start and end parameters
    with freeze_time("2020-02-20 12:00:00+02"):
        get_list_and_assert_events("start=now&end=now", [event5])


@pytest.mark.django_db
def test_start_end_events_without_endtime(api_client, make_event):
    event1 = make_event("1", parser.parse("2020-02-19 23:00:00+02"))
    event2 = make_event("2", parser.parse("2020-02-20 12:00:00+02"))
    event3 = make_event("3", parser.parse("2020-02-21 12:34:56+02"))
    event4 = make_event("4")  # postponed event

    # Start parameter
    get_list_and_assert_events(
        "start=2020-02-19T23:00:00", [event1, event2, event3, event4]
    )
    get_list_and_assert_events("start=2020-02-20T01:00:00", [event2, event3, event4])

    # End parameter
    get_list_and_assert_events("end=2020-02-20T12:00:00", [event1, event2])
    get_list_and_assert_events("end=2020-02-21T23:00:00", [event1, event2, event3])

    # Start and end parameters
    get_list_and_assert_events(
        "start=2020-02-19T23:00:00&end=2020-02-21T12:34:56", [event1, event2, event3]
    )  # noqa E501
    get_list_and_assert_events(
        "start=2020-02-19T23:00:01&end=2020-02-21T12:34:55", [event2]
    )

    # Kulke special case: multiple day event but no specific start or end times, only dates
    event1.start_time = parser.parse("2020-02-19 00:00:00+02")
    event1.end_time = parser.parse("2020-02-21 00:00:00+02")
    event1.has_start_time = False
    event1.has_end_time = False
    event1.save()
    # Kulke special case: single day event, specific start but no end time
    event2.start_time = parser.parse("2020-02-20 18:00:00+02")
    event2.end_time = parser.parse("2020-02-21 00:00:00+02")
    event2.has_start_time = True
    event2.has_end_time = False
    event2.save()

    # Start parameter for Kulke special case
    # long event (no exact start) that already started should be included
    get_list_and_assert_events(
        "start=2020-02-20T12:00:00", [event1, event2, event3, event4]
    )

    # short event (exact start) that already started should not be included
    get_list_and_assert_events("start=2020-02-20T21:00:00", [event1, event3, event4])


@pytest.mark.django_db
def test_keyword_and_text(api_client, event, event2, keyword):
    keyword.name_fi = "lappset"
    keyword.save()
    event.keywords.add(keyword)
    event.save()
    event2.description_fi = "lapset"
    event2.save()
    get_list_and_assert_events("combined_text=lapset", [event, event2])

    event.description_fi = "lapset ja aikuiset"
    event.save()
    get_list_and_assert_events("combined_text=lapset,aikuiset", [event])


@pytest.mark.django_db
def test_keywordset_search(
    api_client,
    event,
    event2,
    event3,
    keyword,
    keyword2,
    keyword3,
    keyword_set,
    keyword_set2,
):
    keyword_set.keywords.set([keyword])
    keyword_set.save()
    keyword_set2.keywords.set([keyword2])
    keyword_set.save()

    event.keywords.set([keyword, keyword3])
    event.save()
    event2.keywords.set([keyword2, keyword3])
    event2.save()
    event3.keywords.set([keyword, keyword2])
    event3.save()

    get_list_and_assert_events(f"keyword_set_AND={keyword_set.id}", [event, event3])
    get_list_and_assert_events(f"keyword_set_AND={keyword_set2.id}", [event2, event3])
    get_list_and_assert_events(
        f"keyword_set_AND={keyword_set.id},{keyword_set2.id}", [event3]
    )
    get_list_and_assert_events(f"keyword_set_OR={keyword_set.id}", [event, event3])
    get_list_and_assert_events(f"keyword_set_OR={keyword_set2.id}", [event2, event3])
    get_list_and_assert_events(
        f"keyword_set_OR={keyword_set.id},{keyword_set2.id}", [event, event2, event3]
    )


@pytest.mark.django_db
def test_keywordset_search_match_audience(
    api_client,
    event,
    event2,
    event3,
    keyword,
    keyword2,
    keyword3,
    keyword_set,
    keyword_set2,
):
    keyword_set.keywords.set([keyword])
    keyword_set.save()
    keyword_set2.keywords.set([keyword2])
    keyword_set.save()

    event.audience.set([keyword, keyword3])
    event.save()
    event2.audience.set([keyword2, keyword3])
    event2.save()
    event3.audience.set([keyword, keyword2])
    event3.save()

    get_list_and_assert_events(f"keyword_set_AND={keyword_set.id}", [event, event3])
    get_list_and_assert_events(f"keyword_set_AND={keyword_set2.id}", [event2, event3])
    get_list_and_assert_events(
        f"keyword_set_AND={keyword_set.id},{keyword_set2.id}", [event3]
    )
    get_list_and_assert_events(f"keyword_set_OR={keyword_set.id}", [event, event3])
    get_list_and_assert_events(f"keyword_set_OR={keyword_set2.id}", [event2, event3])
    get_list_and_assert_events(
        f"keyword_set_OR={keyword_set.id},{keyword_set2.id}", [event, event2, event3]
    )


@pytest.mark.django_db
def test_keyword_or_set_search(
    api_client,
    event,
    event2,
    event3,
    keyword,
    keyword2,
    keyword3,
    keyword_set,
    keyword_set2,
):
    event.keywords.add(keyword, keyword3)
    event.save()
    event2.keywords.add(keyword2, keyword3)
    event2.save()
    event3.keywords.add(keyword, keyword2)
    event3.save()
    load = f"keyword_OR_set1={keyword.id},{keyword2.id}&keyword_OR_set2={keyword3.id}"
    get_list_and_assert_events(load, [event, event2])


@pytest.mark.django_db
def test_keyword_or_set_search_match_audience(
    api_client,
    event,
    event2,
    event3,
    keyword,
    keyword2,
    keyword3,
    keyword_set,
    keyword_set2,
):
    event.audience.add(keyword, keyword3)
    event.save()
    event2.audience.add(keyword2, keyword3)
    event2.save()
    event3.audience.add(keyword, keyword2)
    event3.save()
    load = f"keyword_OR_set1={keyword.id},{keyword2.id}&keyword_OR_set2={keyword3.id}"
    get_list_and_assert_events(load, [event, event2])


@pytest.mark.django_db
def test_event_get_by_type(api_client, event, event2, event3):
    #  default type is General, only general events should be present in the default search
    event2.type_id = Event.TypeId.COURSE
    event2.save()
    event3.type_id = Event.TypeId.VOLUNTEERING
    event3.save()
    get_list_and_assert_events("", [event])
    get_list_and_assert_events("event_type=general", [event])
    get_list_and_assert_events("event_type=general,course", [event, event2])
    get_list_and_assert_events("event_type=course,volunteering", [event2, event3])
    response = get_list_no_code_assert(
        api_client, query_string="event_type=sometypohere"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_event_get_by_id(api_client, event, event2, event3):
    get_list_and_assert_events(f"ids={event.id},{event2.id}", [event, event2])


@pytest.mark.django_db
def test_suitable_for_certain_age(
    api_client, make_event, event, event2, event3, event4
):
    age_upper = 12
    age_lower = 11
    # suitable
    event.audience_min_age = 11
    event.audience_max_age = 13

    # not suitable, min age too high
    event2.audience_min_age = 13

    # not suitable, max age too low
    event3.audience_max_age = 11

    # suitable
    event4.audience_min_age = None
    event4.audience_max_age = 20

    # not suitable, neither of age limits defined
    event5 = make_event(
        "5",
        datetime.now().astimezone(pytz.timezone("UTC")),
        datetime.now().astimezone(pytz.timezone("UTC")) + timedelta(hours=1),
    )
    event5.audience_min_age = None
    event5.audience_max_age = None

    # suitable
    event6 = make_event(
        "6",
        datetime.now().astimezone(pytz.timezone("UTC")),
        datetime.now().astimezone(pytz.timezone("UTC")) + timedelta(hours=1),
    )
    event6.audience_min_age = 11
    event6.audience_max_age = None

    events = [event, event2, event3, event4, event5, event6]
    Event.objects.bulk_update(events, ["audience_min_age", "audience_max_age"])
    get_list_and_assert_events(f"suitable_for={age_upper}", [event, event4, event6])
    get_list_and_assert_events(
        f"suitable_for={age_upper}, {age_lower}", [event, event4, event6]
    )
    get_list_and_assert_events(
        f"suitable_for={age_lower}, {age_upper}", [event, event4, event6]
    )

    response = get_list_no_code_assert(api_client, query_string="suitable_for=error")
    assert (
        str(response.data["detail"])
        == 'suitable_for must be an integer, you passed "error"'
    )

    response = get_list_no_code_assert(api_client, query_string="suitable_for=12,13,14")
    assert (
        str(response.data["detail"])
        == "suitable_for takes at maximum two values, you provided 3"
    )


@pytest.mark.django_db
def test_private_datasource_events(
    api_client, event, event2, event3, other_data_source
):
    get_list_and_assert_events("", [event, event2, event3])
    other_data_source.private = True
    other_data_source.save()
    get_list_and_assert_events("", [event, event3])
    get_list_and_assert_events(f"data_source={other_data_source.id}", [event2])


@pytest.mark.django_db
def test_get_event_list_verify_registration_filter(
    api_client, event, event2, event3, registration, registration2
):
    event.registration = registration
    event.save()
    event2.registration = registration2
    event2.save()
    event3.registration = None
    event3.save()
    get_list_and_assert_events("registration=true", [event, event2])
    get_list_and_assert_events("registration=false", [event3])


@pytest.mark.django_db
def test_get_event_list_maximum_attendee_capacity_filter_gte(
    api_client,
    event,
    event2,
    event3,
):
    event.maximum_attendee_capacity = 10
    event.save()
    event2.maximum_attendee_capacity = 9
    event2.save()
    event3.maximum_attendee_capacity = 8
    event3.save()

    get_list_and_assert_events("maximum_attendee_capacity_gte=9", [event, event2])


@pytest.mark.django_db
def test_get_event_list_maximum_attendee_capacity_filter_gte_when_equal(
    api_client,
    event,
    event2,
    event3,
):
    event.maximum_attendee_capacity = 10
    event.save()
    event2.maximum_attendee_capacity = 9
    event2.save()
    event3.maximum_attendee_capacity = 8
    event3.save()

    get_list_and_assert_events("maximum_attendee_capacity_gte=10", [event])


@pytest.mark.django_db
def test_get_event_list_maximum_attendee_capacity_filter_lte(
    api_client,
    event,
    event2,
    event3,
):
    event.maximum_attendee_capacity = 10
    event.save()
    event2.maximum_attendee_capacity = 9
    event2.save()
    event3.maximum_attendee_capacity = 8
    event3.save()

    get_list_and_assert_events("maximum_attendee_capacity_lte=9", [event2, event3])


@pytest.mark.django_db
def test_get_event_list_maximum_attendee_capacity_filter_lte_when_equal(
    api_client,
    event,
    event2,
    event3,
):
    event.maximum_attendee_capacity = 10
    event.save()
    event2.maximum_attendee_capacity = 9
    event2.save()
    event3.maximum_attendee_capacity = 8
    event3.save()

    get_list_and_assert_events("maximum_attendee_capacity_lte=8", [event3])


@pytest.mark.django_db
def test_get_event_list_minimum_attendee_capacity_filter_gte(
    api_client,
    event,
    event2,
    event3,
):
    event.minimum_attendee_capacity = 10
    event.save()
    event2.minimum_attendee_capacity = 9
    event2.save()
    event3.minimum_attendee_capacity = 8
    event3.save()

    get_list_and_assert_events("minimum_attendee_capacity_gte=9", [event, event2])


@pytest.mark.django_db
def test_get_event_list_minimum_attendee_capacity_filter_gte_when_equal(
    api_client,
    event,
    event2,
    event3,
):
    event.minimum_attendee_capacity = 10
    event.save()
    event2.minimum_attendee_capacity = 9
    event2.save()
    event3.minimum_attendee_capacity = 8
    event3.save()

    get_list_and_assert_events("minimum_attendee_capacity_gte=10", [event])


@pytest.mark.django_db
def test_get_event_list_minimum_attendee_capacity_filter_lte(
    api_client,
    event,
    event2,
    event3,
):
    event.minimum_attendee_capacity = 10
    event.save()
    event2.minimum_attendee_capacity = 9
    event2.save()
    event3.minimum_attendee_capacity = 8
    event3.save()

    get_list_and_assert_events("minimum_attendee_capacity_lte=9", [event2, event3])


@pytest.mark.django_db
def test_get_event_list_minimum_attendee_capacity_filter_lte_when_equal(
    api_client,
    event,
    event2,
    event3,
):
    event.minimum_attendee_capacity = 10
    event.save()
    event2.minimum_attendee_capacity = 9
    event2.save()
    event3.minimum_attendee_capacity = 8
    event3.save()

    get_list_and_assert_events("minimum_attendee_capacity_lte=8", [event3])


@pytest.mark.django_db
def test_sort_events_by_maximum_attendee_capacity(api_client, event, event2, event3):
    event.maximum_attendee_capacity = 10
    event.save()
    event2.maximum_attendee_capacity = 9
    event2.save()
    event3.maximum_attendee_capacity = 8
    event3.save()

    response = get_list(
        api_client=api_client, query_string="sort=-maximum_attendee_capacity"
    )

    results = response.data["data"]
    assert len(results) == 3
    assert results[0]["id"] == event.id
    assert results[1]["id"] == event2.id
    assert results[2]["id"] == event3.id


@pytest.mark.django_db
def test_sort_events_by_minimum_attendee_capacity(api_client, event, event2, event3):
    event.minimum_attendee_capacity = 10
    event.save()
    event2.minimum_attendee_capacity = 9
    event2.save()
    event3.minimum_attendee_capacity = 8
    event3.save()

    response = get_list(
        api_client=api_client, query_string="sort=minimum_attendee_capacity"
    )

    results = response.data["data"]
    assert len(results) == 3
    assert results[0]["id"] == event3.id
    assert results[1]["id"] == event2.id
    assert results[2]["id"] == event.id


@pytest.mark.parametrize(
    "db_field_name,ordering",
    [
        ("enrolment_start_time", "enrolment_start"),
        ("enrolment_start_time", "-enrolment_start"),
        ("enrolment_end_time", "enrolment_end"),
        ("enrolment_end_time", "-enrolment_end"),
    ],
)
@pytest.mark.django_db
def test_sort_events_by_enrolment_start_or_enrolment_end(
    api_client, db_field_name, ordering
):
    event = EventFactory(
        **{db_field_name: localtime().replace(year=2024, month=1, day=1, hour=10)}
    )

    event2 = EventFactory(
        **{db_field_name: localtime().replace(year=2024, month=1, day=1, hour=12)}
    )

    event3 = EventFactory(
        **{db_field_name: localtime().replace(year=2024, month=2, day=1, hour=12)}
    )

    event4 = EventFactory(
        **{db_field_name: localtime().replace(year=2024, month=2, day=2, hour=12)}
    )
    RegistrationFactory(
        event=event4,
        **{db_field_name: localtime().replace(year=2024, month=1, day=1, hour=11)},
    )

    event5 = EventFactory()

    event6 = EventFactory()
    RegistrationFactory(event=event6)

    event7 = EventFactory()
    RegistrationFactory(
        event=event7,
        **{db_field_name: localtime().replace(year=2024, month=2, day=1, hour=11)},
    )

    response = get_list(api_client=api_client, query_string=f"sort={ordering}")

    results = response.data["data"]
    assert len(results) == 7

    if ordering.startswith("-"):
        # Desc.
        assert results[0]["id"] == event3.id  # 1 Feb 2024 at 12.00
        assert (
            results[1]["id"] == event7.id
        )  # 1 Feb 2024 at 11.00 (registration's time)
        assert results[2]["id"] == event2.id  # 1 Jan 2024 at 12.00
        assert (
            results[3]["id"] == event4.id
        )  # 1 Jan 2024 at 11.00 (registration's time)
        assert results[4]["id"] == event.id  # 1 Jan 2024 at 10.00
    else:
        # Asc.
        assert results[0]["id"] == event.id  # 1 Jan 2024 at 10.00
        assert (
            results[1]["id"] == event4.id
        )  # 1 Jan 2024 at 11.00 (registration's time)
        assert results[2]["id"] == event2.id  # 1 Jan 2024 at 12.00
        assert (
            results[3]["id"] == event7.id
        )  # 1 Feb 2024 at 11.00 (registration's time)
        assert results[4]["id"] == event3.id  # 1 Feb 2024 at 12.00

    # Events with null enrolment times will be last. Order might vary.
    assert Counter([results[5]["id"], results[6]["id"]]) == Counter(
        [event5.id, event6.id]
    )


@pytest.mark.parametrize(
    "ordering",
    [
        "enrolment_start_time",
        "-enrolment_start_time",
        "enrolment_end_time",
        "-enrolment_end_time",
    ],
)
@pytest.mark.django_db
def test_sort_events_by_enrolment_start_time_or_enrolment_end_time(
    api_client, ordering
):
    db_field_name = ordering.removeprefix("-")
    now = localtime()

    event = EventFactory(
        **{db_field_name: now.replace(year=2024, month=1, day=1, hour=10)}
    )

    event2 = EventFactory(
        **{db_field_name: now.replace(year=2024, month=1, day=1, hour=12)}
    )

    event3 = EventFactory(
        **{db_field_name: now.replace(year=2024, month=2, day=1, hour=12)}
    )

    event4 = EventFactory(
        **{db_field_name: now.replace(year=2024, month=2, day=2, hour=12)}
    )
    RegistrationFactory(
        event=event4, **{db_field_name: now.replace(year=2024, month=1, day=1, hour=11)}
    )

    event5 = EventFactory()

    event6 = EventFactory()
    RegistrationFactory(event=event6)

    event7 = EventFactory()
    RegistrationFactory(
        event=event7, **{db_field_name: now.replace(year=2024, month=2, day=1, hour=11)}
    )

    response = get_list(api_client=api_client, query_string=f"sort={ordering}")

    results = response.data["data"]
    assert len(results) == 7

    if ordering.startswith("-"):
        # Desc.
        assert Counter(
            [results[0]["id"], results[1]["id"], results[2]["id"]]
        ) == Counter([event5.id, event6.id, event7.id])
        assert results[3]["id"] == event4.id  # 2 Feb 2024 at 12.00
        assert results[4]["id"] == event3.id  # 1 Feb 2024 at 12.00
        assert results[5]["id"] == event2.id  # 1 Jan 2024 at 12.00
        assert results[6]["id"] == event.id  # 1 Jan 2024 at 10.00
    else:
        # Asc.
        assert results[0]["id"] == event.id  # 1 Jan 2024 at 10.00
        assert results[1]["id"] == event2.id  # 1 Jan 2024 at 12.00
        assert results[2]["id"] == event3.id  # 1 Feb 2024 at 12.00
        assert results[3]["id"] == event4.id  # 2 Feb 2024 at 12.00
        assert Counter(
            [results[4]["id"], results[5]["id"], results[6]["id"]]
        ) == Counter([event5.id, event6.id, event7.id])


@pytest.mark.parametrize(
    "ordering",
    [
        "registration__enrolment_start_time",
        "-registration__enrolment_start_time",
        "registration__enrolment_end_time",
        "-registration__enrolment_end_time",
    ],
)
@pytest.mark.django_db
def test_sort_events_by_registration_enrolment_start_time_or_enrolment_end_time(
    api_client, ordering
):
    db_field_name = ordering.split("__")[1]
    now = localtime()

    event = EventFactory()
    RegistrationFactory(
        event=event, **{db_field_name: now.replace(year=2024, month=1, day=1, hour=10)}
    )

    event2 = EventFactory()
    RegistrationFactory(
        event=event2, **{db_field_name: now.replace(year=2024, month=1, day=1, hour=12)}
    )

    event3 = EventFactory()
    RegistrationFactory(
        event=event3, **{db_field_name: now.replace(year=2024, month=2, day=1, hour=12)}
    )

    event4 = EventFactory(
        **{db_field_name: now.replace(year=2024, month=2, day=2, hour=12)}
    )
    RegistrationFactory(
        event=event4, **{db_field_name: now.replace(year=2024, month=2, day=2, hour=12)}
    )

    event5 = EventFactory()

    event6 = EventFactory()
    RegistrationFactory(event=event6)

    event7 = EventFactory()

    response = get_list(api_client=api_client, query_string=f"sort={ordering}")

    results = response.data["data"]
    assert len(results) == 7

    if ordering.startswith("-"):
        # Desc.
        assert Counter(
            [results[0]["id"], results[1]["id"], results[2]["id"]]
        ) == Counter([event5.id, event6.id, event7.id])
        assert results[3]["id"] == event4.id  # 2 Feb 2024 at 12.00
        assert results[4]["id"] == event3.id  # 1 Feb 2024 at 12.00
        assert results[5]["id"] == event2.id  # 1 Jan 2024 at 12.00
        assert results[6]["id"] == event.id  # 1 Jan 2024 at 10.00
    else:
        # Asc.
        assert results[0]["id"] == event.id  # 1 Jan 2024 at 10.00
        assert results[1]["id"] == event2.id  # 1 Jan 2024 at 12.00
        assert results[2]["id"] == event3.id  # 1 Feb 2024 at 12.00
        assert results[3]["id"] == event4.id  # 2 Feb 2024 at 12.00
        assert Counter(
            [results[4]["id"], results[5]["id"], results[6]["id"]]
        ) == Counter([event5.id, event6.id, event7.id])


@pytest.mark.django_db
def test_filter_events_by_enrolment_open_on(api_client):
    now = localtime()

    event = EventFactory()
    RegistrationFactory(
        event=event,
        enrolment_start_time=now.replace(year=2024, month=1, day=1, hour=10),
        enrolment_end_time=now.replace(year=2024, month=1, day=7, hour=10),
    )

    event2 = EventFactory(
        enrolment_start_time=now.replace(year=2024, month=2, day=1, hour=12)
    )

    event3 = EventFactory(
        enrolment_start_time=now.replace(year=2024, month=3, day=1, hour=12),
        enrolment_end_time=now.replace(year=2024, month=3, day=31, hour=12),
    )
    RegistrationFactory(
        event=event3,
        enrolment_start_time=now.replace(year=2025, month=2, day=2, hour=12),
        enrolment_end_time=now.replace(year=2025, month=3, day=2, hour=12),
    )

    event4 = EventFactory(
        enrolment_end_time=now.replace(year=2024, month=12, day=1, hour=12)
    )

    response = get_list(
        api_client=api_client, query_string="enrolment_open_on=2025-02-01"
    )
    results = response.data["data"]
    assert len(results) == 1
    assert results[0]["id"] == event2.id

    response = get_list(
        api_client=api_client, query_string="enrolment_open_on=2025-02-02T13:00:00"
    )
    results = response.data["data"]
    assert len(results) == 2
    assert Counter([result["id"] for result in results]) == Counter(
        [event2.id, event3.id]
    )

    response = get_list(
        api_client=api_client, query_string="enrolment_open_on=2024-01-02T13:00:00"
    )
    results = response.data["data"]
    assert len(results) == 2
    assert Counter([result["id"] for result in results]) == Counter(
        [event.id, event4.id]
    )


@pytest.mark.django_db
def test_event_id_is_audit_logged_on_get_detail(api_client, event):
    response = get_detail(api_client, event.pk)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [event.pk]


@pytest.mark.django_db
def test_event_id_is_audit_logged_on_get_list(api_client, event, event2):
    response = get_list(api_client)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter([event.pk, event2.pk])


@pytest.mark.parametrize(
    "qs,sub_event_query_count,sub_sub_event_query_count",
    [["", 0, 0], ["include=sub_events", 9, 8]],
)
@pytest.mark.django_db
def test_sub_events_increase_query_count_sanely(
    api_client, qs, sub_event_query_count, sub_sub_event_query_count
):
    """
    Rationale: when there is no include=sub_events, the needed information
    for generating the response can be obtained via single query using
    prefetch_related("sub_events"). Since this is done always, the extra
    overhead from sub (sub) events is zero.

    With include, additional queries need to be performed to populate the
    response. Sub events require 8+1 queries, where the +1 is a query to
    discover sub-sub events. Sub-sub events should also require 8 queries.
    """

    def get_num_queries():
        with CaptureQueriesContext(connections[DEFAULT_DB_ALIAS]) as queries:
            response = get_list(api_client, query_string=qs)
            assert response.status_code == status.HTTP_200_OK

        return len(queries)

    event_1 = EventFactory()
    event_2 = EventFactory()

    # Do one warmup list, there's some savepoint/insert happening
    # on first call related to test setup that would give higher
    # than expected number of queries.
    get_num_queries()

    base_count = get_num_queries()

    sub_event_1 = EventFactory(super_event=event_1)
    one_sub_event_count = get_num_queries()

    assert one_sub_event_count == base_count + sub_event_query_count

    # More than one sub event should NOT increase number of queries
    sub_event_2 = EventFactory(super_event=event_2)
    assert get_num_queries() == one_sub_event_count

    EventFactory(super_event=sub_event_1)
    one_sub_sub_event_count = get_num_queries()
    assert one_sub_sub_event_count == one_sub_event_count + sub_sub_event_query_count

    # More than one sub-sub event should NOT increase number of queries
    EventFactory(super_event=sub_event_2)
    EventFactory(super_event=sub_event_2)

    assert get_num_queries() == one_sub_sub_event_count


@pytest.mark.django_db
def test_get_event_with_offer_and_offer_price_groups(api_client, event):
    offer = OfferFactory(event=event)
    OfferPriceGroupFactory(offer=offer)

    response = get_detail(api_client, event.pk)
    assert response.status_code == status.HTTP_200_OK

    assert len(response.data["offers"]) == 1
    assert_offer_fields_exist(response.data["offers"][0])

    assert len(response.data["offers"][0]["offer_price_groups"]) == 1
    assert_offer_price_group_fields_exist(
        response.data["offers"][0]["offer_price_groups"][0]
    )


class FilterEventsByRegistrationCapacitiesV1TestCase(TestCase, EventsListTestCaseMixin):
    @classmethod
    def setUpTestData(cls):
        cls.list_url = reverse("event-list", version="v1")

    def test_get_event_list_registration_remaining_attendee_capacity_gte(self):
        registration = RegistrationFactory(remaining_attendee_capacity=10)
        registration2 = RegistrationFactory(remaining_attendee_capacity=5)
        registration3 = RegistrationFactory(remaining_attendee_capacity=1)

        for capacity, events in [
            (1, [registration.event, registration2.event, registration3.event]),
            (5, [registration.event, registration2.event]),
            (10, [registration.event]),
            (11, []),
        ]:
            with self.subTest():
                self._get_list_and_assert_events(
                    f"registration__remaining_attendee_capacity__gte={capacity}", events
                )

    def test_get_event_list_registration_remaining_waiting_list_capacity_gte(self):
        registration = RegistrationFactory(remaining_waiting_list_capacity=10)
        registration2 = RegistrationFactory(remaining_waiting_list_capacity=5)
        registration3 = RegistrationFactory(remaining_waiting_list_capacity=1)

        for capacity, events in [
            (1, [registration.event, registration2.event, registration3.event]),
            (5, [registration.event, registration2.event]),
            (10, [registration.event]),
            (11, []),
        ]:
            with self.subTest():
                self._get_list_and_assert_events(
                    f"registration__remaining_waiting_list_capacity__gte={capacity}",
                    events,
                )

    def test_get_event_list_registration_remaining_attendee_capacity_isnull(self):
        registration = RegistrationFactory(remaining_attendee_capacity=10)
        registration2 = RegistrationFactory(remaining_attendee_capacity=None)
        registration3 = RegistrationFactory(remaining_attendee_capacity=1)

        for capacity, events in [
            (1, [registration2.event]),
            (0, [registration.event, registration3.event]),
            (True, [registration2.event]),
            (False, [registration.event, registration3.event]),
        ]:
            with self.subTest():
                self._get_list_and_assert_events(
                    f"registration__remaining_attendee_capacity__isnull={capacity}",
                    events,
                )

    def test_get_event_list_registration_remaining_waiting_list_capacity_isnull(self):
        registration = RegistrationFactory(remaining_waiting_list_capacity=10)
        registration2 = RegistrationFactory(remaining_waiting_list_capacity=None)
        registration3 = RegistrationFactory(remaining_waiting_list_capacity=1)

        for capacity, events in [
            (1, [registration2.event]),
            (0, [registration.event, registration3.event]),
            (True, [registration2.event]),
            (False, [registration.event, registration3.event]),
        ]:
            with self.subTest():
                self._get_list_and_assert_events(
                    f"registration__remaining_waiting_list_capacity__isnull={capacity}",
                    events,
                )
