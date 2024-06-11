from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytz
from dateutil.parser import parse as dateutil_parse
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone, translation
from django.utils.encoding import force_str
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.api import KeywordSerializer
from events.auth import ApiKeyUser
from events.models import Event, Keyword, Place
from events.tests.utils import assert_event_data_is_equal
from registrations.enums import VatPercentage
from registrations.models import OfferPriceGroup, PriceGroup
from registrations.tests.factories import PriceGroupFactory

from .factories import KeywordFactory
from .utils import versioned_reverse as reverse


@pytest.fixture
def list_url():
    return reverse("event-list")


# === util methods ===


def create_with_post(api_client, event_data, data_source=None):
    create_url = reverse("event-list")
    if data_source:
        api_client.credentials(apikey=data_source.api_key)

    # save with post
    response = api_client.post(create_url, event_data, format="json")
    assert response.status_code == 201, str(response.content)

    # double-check with get
    resp2 = api_client.get(response.data["@id"])
    assert resp2.status_code == 200, str(response.content)

    return resp2


# === tests ===


@pytest.mark.django_db
def test__create_a_minimal_event_with_post(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)


@pytest.mark.django_db
def test__create_a_minimal_event_with_naive_datetime(
    api_client, minimal_event_dict, user
):
    api_client.force_authenticate(user=user)
    minimal_event_dict["start_time"] = (datetime.now() + timedelta(days=1)).isoformat()
    response = create_with_post(api_client, minimal_event_dict)

    # API should have assumed UTC datetime
    minimal_event_dict["start_time"] = (
        pytz.utc.localize(dateutil_parse(minimal_event_dict["start_time"]))
        .isoformat()
        .replace("+00:00", "Z")
    )
    assert_event_data_is_equal(minimal_event_dict, response.data)


@pytest.mark.django_db
def test__cannot_create_an_event_with_existing_id(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user=user)
    minimal_event_dict["id"] = settings.SYSTEM_DATA_SOURCE_ID + ":1"
    create_with_post(api_client, minimal_event_dict)
    response = api_client.post(reverse("event-list"), minimal_event_dict, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test__api_key_with_organization_can_create_an_event(
    api_client, minimal_event_dict, data_source, organization
):
    data_source.owner = organization
    data_source.save()

    response = create_with_post(api_client, minimal_event_dict, data_source)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    assert ApiKeyUser.objects.all().count() == 1


@pytest.mark.django_db
def test__api_key_with_organization_event_create_sets_correct_publisher(
    api_client, minimal_event_dict, data_source, organization
):
    """Empty publisher in data should set the data source owner as the publisher."""
    del minimal_event_dict["publisher"]
    data_source.owner = organization
    data_source.save()

    response = create_with_post(api_client, minimal_event_dict, data_source)

    minimal_event_dict["publisher"] = organization.id
    assert_event_data_is_equal(minimal_event_dict, response.data)


@pytest.mark.django_db
def test__api_key_with_organization_can_create_a_suborganization_event(
    api_client, minimal_event_dict, data_source, organization, organization2
):
    data_source.owner = organization
    data_source.save()

    organization2.parent = organization
    organization2.save()
    minimal_event_dict["publisher"] = organization2.id

    response = create_with_post(api_client, minimal_event_dict, data_source)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    assert ApiKeyUser.objects.all().count() == 1


@pytest.mark.django_db
def test__api_key_with_organization_cannot_create_a_superorganization_event(
    api_client, minimal_event_dict, other_data_source, organization, organization2
):
    other_data_source.owner = organization2
    other_data_source.save()

    organization2.parent = organization
    organization2.save()

    api_client.credentials(apikey=other_data_source.api_key)
    response = api_client.post(reverse("event-list"), minimal_event_dict, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test__api_key_with_another_organization_can_create_an_event(
    api_client,
    minimal_event_dict,
    data_source,
    organization,
    other_data_source,
    organization2,
):
    data_source.owner = organization
    data_source.save()
    other_data_source.owner = organization2
    other_data_source.save()

    response = create_with_post(api_client, minimal_event_dict, data_source)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    assert ApiKeyUser.objects.all().count() == 1

    minimal_event_dict["publisher"] = organization2.id
    response = create_with_post(api_client, minimal_event_dict, other_data_source)
    assert_event_data_is_equal(minimal_event_dict, response.data)
    assert ApiKeyUser.objects.all().count() == 2


@pytest.mark.django_db
def test__api_key_without_organization_cannot_create_an_event(
    api_client, minimal_event_dict, data_source
):
    api_client.credentials(apikey=data_source.api_key)
    response = api_client.post(reverse("event-list"), minimal_event_dict, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test__unknown_api_key_cannot_create_an_event(api_client, minimal_event_dict):
    api_client.credentials(apikey="unknown")
    response = api_client.post(reverse("event-list"), minimal_event_dict, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test__empty_api_key_cannot_create_an_event(api_client, minimal_event_dict):
    api_client.credentials(apikey="")
    response = api_client.post(reverse("event-list"), minimal_event_dict, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test__cannot_create_an_event_ending_before_start_time(
    list_url, api_client, minimal_event_dict, user
):
    api_client.force_authenticate(user=user)
    minimal_event_dict["end_time"] = (timezone.now() + timedelta(days=1)).isoformat()
    minimal_event_dict["start_time"] = (timezone.now() + timedelta(days=2)).isoformat()
    response = api_client.post(list_url, minimal_event_dict, format="json")
    assert response.status_code == 400
    assert "end_time" in response.data


@pytest.mark.django_db
def test__create_a_draft_event_without_location_and_keyword(
    list_url, api_client, minimal_event_dict, user
):
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop("location")
    minimal_event_dict.pop("keywords")
    minimal_event_dict["publication_status"] = "draft"
    response = create_with_post(api_client, minimal_event_dict)
    assert_event_data_is_equal(minimal_event_dict, response.data)

    # the drafts should not be visible to unauthorized users
    api_client.logout()
    resp2 = api_client.get(response.data["@id"])
    assert "@id" not in resp2.data


@pytest.mark.django_db
def test__cannot_create_a_draft_event_without_a_name(
    list_url, api_client, minimal_event_dict, user
):
    api_client.force_authenticate(user=user)
    minimal_event_dict["publication_status"] = "draft"
    minimal_event_dict["name"] = {"fi": None}
    response = api_client.post(list_url, minimal_event_dict, format="json")
    assert response.status_code == 400
    assert "name" in response.data
    minimal_event_dict.pop("name")
    response = api_client.post(list_url, minimal_event_dict, format="json")
    assert response.status_code == 400
    assert "name" in response.data


@pytest.mark.django_db
def test__cannot_publish_an_event_without_start_time(
    list_url, api_client, minimal_event_dict, user
):
    api_client.force_authenticate(user=user)
    minimal_event_dict["start_time"] = None
    response = api_client.post(list_url, minimal_event_dict, format="json")
    assert response.status_code == 400
    assert "start_time" in response.data
    del minimal_event_dict["start_time"]
    response2 = api_client.post(list_url, minimal_event_dict, format="json")
    assert response2.status_code == 400
    assert "start_time" in response2.data


@pytest.mark.django_db
def test__cannot_publish_an_event_without_description(
    list_url, api_client, minimal_event_dict, user
):
    api_client.force_authenticate(user=user)
    minimal_event_dict["description"] = {"fi": None}
    response = api_client.post(list_url, minimal_event_dict, format="json")
    assert response.status_code == 400
    assert "description" in response.data
    del minimal_event_dict["description"]
    response2 = api_client.post(list_url, minimal_event_dict, format="json")
    assert response2.status_code == 400
    assert "description" in response2.data


@pytest.mark.django_db
def test__cannot_publish_an_event_without_location(
    list_url, api_client, minimal_event_dict, user
):
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop("location")
    response = api_client.post(list_url, minimal_event_dict, format="json")
    assert response.status_code == 400
    assert "location" in response.data


@pytest.mark.django_db
def test__cannot_publish_an_event_without_keywords(
    list_url, api_client, minimal_event_dict, user
):
    api_client.force_authenticate(user=user)
    minimal_event_dict.pop("keywords")
    response = api_client.post(list_url, minimal_event_dict, format="json")
    assert response.status_code == 400
    assert "keywords" in response.data


@pytest.mark.django_db
def test__keyword_n_events_updated(
    list_url, api_client, minimal_event_dict, user, data_source
):
    api_client.force_authenticate(user=user)
    api_client.post(list_url, minimal_event_dict, format="json")
    call_command("update_n_events")
    assert Keyword.objects.get(id=data_source.id + ":test").n_events == 1


@pytest.mark.django_db
def test__location_n_events_updated(
    list_url, api_client, minimal_event_dict, user, data_source
):
    api_client.force_authenticate(user=user)
    api_client.post(list_url, minimal_event_dict, format="json")
    call_command("update_n_events")
    assert Place.objects.get(id=data_source.id + ":test_location").n_events == 1


@pytest.mark.django_db
def test__create_a_complex_event_with_post(api_client, complex_event_dict, user):
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, complex_event_dict)
    assert_event_data_is_equal(complex_event_dict, response.data)


@pytest.mark.freeze_time("2023-01-01")
@pytest.mark.django_db
def test__autopopulated_fields_at_create(
    api_client,
    minimal_event_dict,
    user,
    user2,
    other_data_source,
    organization,
    organization2,
):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)

    event = Event.objects.get(id=response.data["id"])
    assert event.created_by == user
    assert event.last_modified_by == user
    assert event.created_time is not None
    assert event.last_modified_time is not None
    assert event.data_source.id == settings.SYSTEM_DATA_SOURCE_ID
    assert event.publisher == organization
    # events are automatically marked as ending at midnight, local time
    assert event.end_time == timezone.localtime(
        timezone.now() + timedelta(days=2)
    ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
    assert event.has_end_time is False


@pytest.mark.xfail(reason="potential DST shenanigans")
@pytest.mark.freeze_time("2023-01-01")
@pytest.mark.django_db
def test__autopopulated_fields_at_create_dst(
    api_client,
    minimal_event_dict,
    user,
    user2,
    other_data_source,
    organization,
    organization2,
):
    # create an event
    api_client.force_authenticate(user=user)
    response = create_with_post(api_client, minimal_event_dict)

    event = Event.objects.get(id=response.data["id"])
    assert event.created_by == user
    assert event.last_modified_by == user
    assert event.created_time is not None
    assert event.last_modified_time is not None
    assert event.data_source.id == settings.SYSTEM_DATA_SOURCE_ID
    assert event.publisher == organization
    # events are automatically marked as ending at midnight, local time
    assert event.end_time == timezone.localtime(
        timezone.now() + timedelta(days=2)
    ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
    assert event.has_end_time is False


# the following values may not be posted
@pytest.mark.django_db
@pytest.mark.parametrize(
    "non_permitted_input,non_permitted_response",
    [
        ({"id": "not_allowed:1"}, 400),  # may not fake id
        ({"data_source": "theotherdatasourceid"}, 400),  # may not fake data source
        ({"publisher": "test_organization2"}, 400),  # may not fake organization
    ],
)
def test__non_editable_fields_at_create(
    api_client,
    minimal_event_dict,
    list_url,
    user,
    non_permitted_input,
    non_permitted_response,
):
    api_client.force_authenticate(user)

    minimal_event_dict.update(non_permitted_input)

    response = api_client.post(list_url, minimal_event_dict, format="json")
    assert response.status_code == non_permitted_response
    if non_permitted_response >= 400:
        # check that there is an error message for the corresponding field
        assert list(non_permitted_input)[0] in response.data


# the following values may not be posted
@pytest.mark.django_db
@pytest.mark.parametrize(
    "non_permitted_input,non_permitted_response",
    [
        ({"id": "not_allowed:1"}, 400),  # may not fake id
        ({"data_source": "theotherdatasourceid"}, 400),  # may not fake data source
        ({"publisher": "test_organization2"}, 400),  # may not fake organization
    ],
)
def test__apikey_non_editable_fields_at_create(
    api_client,
    minimal_event_dict,
    list_url,
    organization,
    data_source,
    non_permitted_input,
    non_permitted_response,
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    minimal_event_dict.update(non_permitted_input)

    response = api_client.post(list_url, minimal_event_dict, format="json")
    assert response.status_code == non_permitted_response
    if non_permitted_response >= 400:
        # check that there is an error message for the corresponding field
        assert list(non_permitted_input)[0] in response.data


# location field is used for JSONLDRelatedField tests
@pytest.mark.django_db
@pytest.mark.parametrize(
    "ld_input,ld_expected",
    [
        (
            {
                "location": {
                    "@id": "/v1/place/"
                    + settings.SYSTEM_DATA_SOURCE_ID
                    + ":test_location/"
                }
            },
            201,
        ),
        ({"location": {"@id": ""}}, 400),  # field required
        ({"location": {"foo": "bar"}}, 400),  # incorrect json
        (
            {
                "location": "/v1/place/"
                + settings.SYSTEM_DATA_SOURCE_ID
                + ":test_location/"
            },
            400,
        ),  # incorrect json
        ({"location": 7}, 400),  # incorrect json
        ({"location": None}, 400),  # cannot be null
        ({}, 400),  # field required
    ],
)
def test__jsonld_related_field(
    api_client, minimal_event_dict, list_url, place, user, ld_input, ld_expected
):
    api_client.force_authenticate(user)

    del minimal_event_dict["location"]
    minimal_event_dict.update(ld_input)

    response = api_client.post(list_url, minimal_event_dict, format="json")
    assert response.status_code == ld_expected
    if ld_expected >= 400:
        # check that there is a error message for location field
        assert "location" in response.data


@pytest.mark.django_db
def test_start_time_and_end_time_validation(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)

    minimal_event_dict["start_time"] = (
        (timezone.now() - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    )
    minimal_event_dict["end_time"] = (
        (timezone.now() - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    )

    with translation.override("en"):
        response = api_client.post(
            reverse("event-list"), minimal_event_dict, format="json"
        )
    assert response.status_code == 400
    assert (
        "End time cannot be in the past. Please set a future end time."
        in response.data["end_time"]
    )


@pytest.mark.django_db
def test_start_time_and_end_time_validation_with_past_events_allowed(
    api_client, minimal_event_dict, user, data_source
):
    api_client.force_authenticate(user)

    data_source.create_past_events = True
    data_source.save()

    minimal_event_dict["start_time"] = (
        (timezone.now() - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    )
    minimal_event_dict["end_time"] = (
        (timezone.now() - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    )

    response = create_with_post(api_client, minimal_event_dict, data_source)
    assert_event_data_is_equal(minimal_event_dict, response.data)


@pytest.mark.django_db
def test_description_and_short_description_required_in_name_languages(
    api_client, minimal_event_dict, user
):
    api_client.force_authenticate(user)

    minimal_event_dict["name"] = {"fi": "nimi", "sv": "namn"}
    minimal_event_dict["short_description"] = {"fi": "lyhyt kuvaus"}
    minimal_event_dict["description"] = {"sv": "description in swedish"}

    with translation.override("en"):
        response = api_client.post(
            reverse("event-list"), minimal_event_dict, format="json"
        )

    # there should be only one error
    assert len(response.data["short_description"]) == 1
    assert len(response.data["description"]) == 1

    assert (
        force_str(response.data["short_description"]["sv"])
        == "This field must be specified before an event is published."
    )
    assert (
        force_str(response.data["description"]["fi"])
        == "This field must be specified before an event is published."
    )


@pytest.mark.django_db
def test_short_description_cannot_exceed_160_chars(
    api_client, minimal_event_dict, user
):
    api_client.force_authenticate(user)

    minimal_event_dict["short_description"]["fi"] = "x" * 161

    with translation.override("en"):
        response = api_client.post(
            reverse("event-list"), minimal_event_dict, format="json"
        )
    assert response.status_code == 400
    assert force_str(
        response.data["short_description"]["fi"]
        == "Short description length must be 160 characters or less"
    )


@pytest.mark.django_db
def test_description_may_contain_html(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)

    for lang in minimal_event_dict["description"]:
        minimal_event_dict["description"][lang] = " ".join(settings.BLEACH_ALLOWED_TAGS)

    response = api_client.post(reverse("event-list"), minimal_event_dict, format="json")
    assert response.status_code == 201
    for lang in minimal_event_dict["description"]:
        assert response.data["description"][lang] == " ".join(
            settings.BLEACH_ALLOWED_TAGS
        )


@pytest.mark.django_db
def test_description_may_only_contain_safe_tags(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)

    for lang in minimal_event_dict["description"]:
        minimal_event_dict["description"][lang] = "<script/>"

    response = api_client.post(reverse("event-list"), minimal_event_dict, format="json")
    assert response.status_code == 201
    for lang in minimal_event_dict["description"]:
        assert response.data["description"][lang] != "<script/>"


@pytest.mark.django_db
def test_other_fields_may_not_contain_html(api_client, complex_event_dict, user):
    text_fields = ("location_extra_info", "short_description", "provider", "name")
    api_client.force_authenticate(user)

    for field in text_fields:
        for lang in complex_event_dict[field]:
            complex_event_dict[field][lang] = "<br/>"

    response = api_client.post(reverse("event-list"), complex_event_dict, format="json")
    assert response.status_code == 201
    for field in text_fields:
        for lang in complex_event_dict[field]:
            assert response.data[field][lang] != "<br/>"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "offers, expected",
    [
        ([{"is_free": True}], 201),
        ([{"is_free": False, "price": {"fi": 4}}], 201),
        ([{"description": {"fi": "foo"}}, {"is_free": True}], 201),
        ([{"is_free": False}], 201),
        ([], 400),
    ],
)
def test_price_info_options(api_client, minimal_event_dict, user, offers, expected):
    api_client.force_authenticate(user)
    minimal_event_dict["offers"] = offers

    with translation.override("en"):
        response = api_client.post(
            reverse("event-list"), minimal_event_dict, format="json"
        )

    assert response.status_code == expected
    if expected == 400:
        assert (
            force_str(response.data["offers"][0])
            == "Price info must be specified before an event is published."
        )


@pytest.mark.django_db
def test_no_html_in_price_info(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)
    minimal_event_dict["offers"] = [
        {"description": {"fi": "<br/>"}, "price": {"fi": "<br/>"}, "is_free": False}
    ]

    response = api_client.post(reverse("event-list"), minimal_event_dict, format="json")
    assert response.status_code == 201
    assert response.data["offers"][0]["description"]["fi"] != "<br/>"
    assert response.data["offers"][0]["price"]["fi"] != "<br/>"


@pytest.mark.parametrize(
    "name, is_valid",
    [
        ({"sv": "namn"}, True),
        ({"foo": "bar"}, False),
        ({}, False),
        (None, False),
    ],
)
@pytest.mark.django_db
def test_name_required_in_some_language(
    api_client, minimal_event_dict, user, name, is_valid
):
    api_client.force_authenticate(user)

    minimal_event_dict["name"] = name

    with translation.override("en"):
        response = api_client.post(
            reverse("event-list"), minimal_event_dict, format="json"
        )

    if is_valid:
        assert response.status_code == 201
    else:
        assert response.status_code == 400

    if not is_valid:
        assert force_str(response.data["name"][0]) == "The name must be specified."


@pytest.mark.django_db
def test_multiple_event_creation(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)
    minimal_event_dict_2 = deepcopy(minimal_event_dict)
    minimal_event_dict_2["name"]["fi"] = "testaus_2"

    response = api_client.post(
        reverse("event-list"), [minimal_event_dict, minimal_event_dict_2], format="json"
    )
    assert response.status_code == 201

    event_names = set(Event.objects.values_list("name_fi", flat=True))
    assert event_names == {"testaus", "testaus_2"}


@pytest.mark.django_db
def test_multiple_event_creation_missing_data_fails(
    api_client, minimal_event_dict, user
):
    api_client.force_authenticate(user)
    minimal_event_dict_2 = deepcopy(minimal_event_dict)
    minimal_event_dict_2.pop(
        "name"
    )  # name is required, so the event update event should fail

    response = api_client.post(
        reverse("event-list"), [minimal_event_dict, minimal_event_dict_2], format="json"
    )
    assert response.status_code == 400
    assert "name" in response.data[1]

    # the first event should not be created either
    assert Event.objects.count() == 0


@pytest.mark.django_db
def test_multiple_event_creation_non_allowed_data_fails(
    api_client, minimal_event_dict, other_data_source, user
):
    api_client.force_authenticate(user)
    minimal_event_dict_2 = deepcopy(minimal_event_dict)
    minimal_event_dict_2["data_source"] = (
        other_data_source.id
    )  # non-allowed data source

    response = api_client.post(
        reverse("event-list"), [minimal_event_dict, minimal_event_dict_2], format="json"
    )
    assert response.status_code == 403
    assert "data_source" in response.data

    # the first event should not be created either
    assert Event.objects.count() == 0


@pytest.mark.django_db
def test_create_super_event_with_subevents(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user)
    sub_event_dict_1 = deepcopy(minimal_event_dict)
    sub_event_dict_2 = deepcopy(minimal_event_dict)
    minimal_event_dict["super_event_type"] = Event.SuperEventType.RECURRING

    response = api_client.post(reverse("event-list"), minimal_event_dict, format="json")
    assert response.status_code == 201
    super_event_url = response.data["@id"]
    super_event_id = response.data["id"]

    sub_event_dict_1["super_event"] = {"@id": super_event_url}
    sub_event_dict_1["name"]["fi"] = "sub event 1"
    sub_event_dict_2["super_event"] = {"@id": super_event_url}
    sub_event_dict_2["name"]["fi"] = "sub event 2"

    response = api_client.post(
        reverse("event-list"), [sub_event_dict_1, sub_event_dict_2], format="json"
    )
    assert response.status_code == 201

    super_event = Event.objects.get(id=super_event_id)
    assert super_event.super_event_type == Event.SuperEventType.RECURRING
    # there shouldn't be other recurring super events
    assert (
        Event.objects.filter(super_event_type=Event.SuperEventType.RECURRING).count()
        == 1
    )

    sub_event_names = set(
        [sub_event.name_fi for sub_event in super_event.sub_events.all()]
    )
    assert sub_event_names == {"sub event 1", "sub event 2"}


@pytest.mark.django_db
def test__create_event_with_image_not_exists(
    api_client, data_source, organization, minimal_event_dict, user
):
    api_client.force_authenticate(user=user)
    minimal_event_dict["images"] = [
        {
            "@id": "http://testserver/v1/image/1/",
            "name": "image",
            "data_source": data_source.id,
            "publisher": organization.id,
            "url": "https://example.com/image.jpg",
        }
    ]
    create_url = reverse("event-list")
    response = api_client.post(create_url, minimal_event_dict, format="json")
    assert response.status_code == 400, response.data
    assert response.data["images"][0].code == "does_not_exist"


@pytest.mark.django_db
def test__create_event_with_image_without_id(
    api_client, data_source, organization, minimal_event_dict, user
):
    api_client.force_authenticate(user=user)
    minimal_event_dict["images"] = [
        {
            "name": "image",
            "data_source": data_source.id,
            "publisher": organization.id,
            "url": "https://example.com/image.jpg",
        }
    ]
    create_url = reverse("event-list")
    response = api_client.post(create_url, minimal_event_dict, format="json")
    assert response.status_code == 400, response.data
    assert "@id field missing" in response.json()["images"][0], response.data


@pytest.mark.django_db
def test__deprecated_keyword(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user=user)
    deprecated_kw = KeywordFactory(deprecated=True)
    minimal_event_dict["keywords"] = [
        {"@id": reverse(KeywordSerializer.view_name, kwargs={"pk": deprecated_kw.id})}
    ]
    create_url = reverse("event-list")
    response = api_client.post(create_url, minimal_event_dict, format="json")
    assert response.status_code == 400, response.data
    assert "keywords" in response.data
    assert len(response.data["keywords"]) == 1
    assert (
        str(response.data["keywords"][0])
        == f"Deprecated keyword not allowed ({deprecated_kw.pk})"
    )


@pytest.mark.django_db
def test__deprecated_audience(api_client, minimal_event_dict, user):
    api_client.force_authenticate(user=user)
    deprecated_kw = KeywordFactory(deprecated=True)
    minimal_event_dict["audience"] = [
        {"@id": reverse(KeywordSerializer.view_name, kwargs={"pk": deprecated_kw.id})}
    ]
    create_url = reverse("event-list")
    response = api_client.post(create_url, minimal_event_dict, format="json")
    assert response.status_code == 400, response.data
    assert "audience" in response.data
    assert len(response.data["audience"]) == 1
    assert (
        str(response.data["audience"][0])
        == f"Deprecated keyword not allowed ({deprecated_kw.pk})"
    )


@pytest.mark.django_db
def test_event_id_is_audit_logged_on_post(user_api_client, minimal_event_dict):
    response = create_with_post(user_api_client, minimal_event_dict)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data["id"]
    ]


@pytest.mark.django_db
def test_create_event_with_offer_price_groups(
    user_api_client, organization, minimal_event_dict
):
    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()
    custom_price_group = PriceGroupFactory(publisher=organization)

    assert OfferPriceGroup.objects.count() == 0

    minimal_event_dict["offers"] = [
        {
            "is_free": False,
            "price": {"fi": "10 - 15.55 €"},
            "offer_price_groups": [
                {
                    "price_group": default_price_group.pk,
                    "price": Decimal("10"),
                    "vat_percentage": VatPercentage.VAT_24.value,
                },
                {
                    "price_group": custom_price_group.pk,
                    "price": Decimal("15.55"),
                    "vat_percentage": VatPercentage.VAT_10.value,
                },
            ],
        }
    ]
    response = user_api_client.post(
        reverse("event-list"), minimal_event_dict, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert len(response.data["offers"][0]["offer_price_groups"]) == 2

    assert OfferPriceGroup.objects.count() == 2
    assert (
        OfferPriceGroup.objects.filter(
            price_group=default_price_group.pk,
            price=minimal_event_dict["offers"][0]["offer_price_groups"][0]["price"],
            vat_percentage=minimal_event_dict["offers"][0]["offer_price_groups"][0][
                "vat_percentage"
            ],
            price_without_vat=Decimal("8.06"),
            vat=Decimal("1.94"),
        ).count()
        == 1
    )
    assert (
        OfferPriceGroup.objects.filter(
            price_group=custom_price_group.pk,
            price=minimal_event_dict["offers"][0]["offer_price_groups"][1]["price"],
            vat_percentage=minimal_event_dict["offers"][0]["offer_price_groups"][1][
                "vat_percentage"
            ],
            price_without_vat=Decimal("14.14"),
            vat=Decimal("1.41"),
        ).count()
        == 1
    )


@pytest.mark.parametrize(
    "price,vat_percentage",
    [
        (Decimal("10"), VatPercentage.VAT_24.value),
        (Decimal("10"), VatPercentage.VAT_0.value),
        (None, VatPercentage.VAT_24.value),
    ],
)
@pytest.mark.django_db
def test_create_event_with_a_free_offer_price_group(
    user_api_client, organization, minimal_event_dict, price, vat_percentage
):
    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=True
    ).first()

    assert OfferPriceGroup.objects.count() == 0

    price_group_data = {
        "price_group": default_price_group.pk,
        "vat_percentage": vat_percentage,
    }
    if price is not None:
        price_group_data["price"] = price

    minimal_event_dict["offers"] = [
        {
            "is_free": False,
            "price": {"fi": "? €"},
            "offer_price_groups": [price_group_data],
        }
    ]
    response = user_api_client.post(
        reverse("event-list"), minimal_event_dict, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert len(response.data["offers"][0]["offer_price_groups"]) == 1

    assert OfferPriceGroup.objects.count() == 1

    offer_price_group = OfferPriceGroup.objects.first()
    assert offer_price_group.price == Decimal("0")
    assert offer_price_group.vat_percentage == vat_percentage
    assert offer_price_group.price_without_vat == Decimal("0")
    assert offer_price_group.vat == Decimal("0")


@pytest.mark.parametrize(
    "price,vat_percentage",
    [
        (-10, VatPercentage.VAT_24.value),
        (Decimal("-10"), VatPercentage.VAT_24.value),
        (Decimal("-10"), VatPercentage.VAT_0.value),
        (Decimal("10.123"), VatPercentage.VAT_24.value),
        (Decimal("10.1234"), VatPercentage.VAT_24.value),
        (None, VatPercentage.VAT_24.value),
    ],
)
@pytest.mark.django_db
def test_cannot_create_event_with_wrong_or_missing_offer_price_group_price(
    user_api_client, organization, minimal_event_dict, price, vat_percentage
):
    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    assert OfferPriceGroup.objects.count() == 0

    price_group_data = {
        "price_group": default_price_group.pk,
        "vat_percentage": vat_percentage,
    }
    if price is not None:
        price_group_data["price"] = price

    minimal_event_dict["offers"] = [
        {
            "is_free": False,
            "price": {"fi": "? €"},
            "offer_price_groups": [price_group_data],
        }
    ]
    response = user_api_client.post(
        reverse("event-list"), minimal_event_dict, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert OfferPriceGroup.objects.count() == 0


@pytest.mark.parametrize(
    "vat_percentage",
    [
        1,
        12,
        100,
        Decimal("1"),
        Decimal("12"),
        Decimal("100"),
        Decimal("24.1"),
        "",
        None,
    ],
)
@pytest.mark.django_db
def test_cannot_create_event_with_wrong_or_missing_offer_price_group_vat_percentage(
    user_api_client, organization, minimal_event_dict, vat_percentage
):
    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    assert OfferPriceGroup.objects.count() == 0

    price_group_data = {
        "price_group": default_price_group.pk,
        "price": Decimal("10"),
    }
    if vat_percentage is not None:
        price_group_data["vat_percentage"] = vat_percentage

    minimal_event_dict["offers"] = [
        {
            "is_free": False,
            "price": {"fi": "? €"},
            "offer_price_groups": [price_group_data],
        }
    ]
    response = user_api_client.post(
        reverse("event-list"), minimal_event_dict, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert OfferPriceGroup.objects.count() == 0


@pytest.mark.django_db
def test_cannot_create_event_with_duplicate_offer_price_groups(
    user_api_client, organization, minimal_event_dict
):
    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    assert OfferPriceGroup.objects.count() == 0

    price_group_data = {
        "price_group": default_price_group.pk,
        "price": Decimal("10"),
        "vat_percentage": VatPercentage.VAT_24.value,
    }
    minimal_event_dict["offers"] = [
        {
            "is_free": False,
            "price": {"fi": "? €"},
            "offer_price_groups": [price_group_data, price_group_data],
        }
    ]
    response = user_api_client.post(
        reverse("event-list"), minimal_event_dict, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["offers"][0]["offer_price_groups"][1]["price_group"][0] == (
        f"Offer price group with price_group {default_price_group} already exists."
    )

    assert OfferPriceGroup.objects.count() == 0


@pytest.mark.django_db
def test_create_event_with_large_minimum_and_maximum_attendee_capacity(
    user_api_client,
    minimal_event_dict,
):
    minimal_event_dict["minimum_attendee_capacity"] = 500000
    minimal_event_dict["maximum_attendee_capacity"] = 1000000

    assert Event.objects.count() == 0

    response = user_api_client.post(
        reverse("event-list"), minimal_event_dict, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED

    assert Event.objects.count() == 1

    event = Event.objects.first()
    assert event.minimum_attendee_capacity == 500000
    assert event.maximum_attendee_capacity == 1000000
