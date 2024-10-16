import io
from http.client import HTTPMessage, HTTPResponse
from unittest.mock import Mock, patch

import factory
import pytest
import pytz
from django.conf import settings as django_settings
from django.utils import timezone
from django_orghierarchy.models import Organization
from faker import Faker

from events.importer.espoo import (
    EspooImporter,
    EspooImporterError,
    _build_pre_map_to_id,
    _get_data,
    _get_origin_objs,
    _import_origin_obj,
    _import_origin_objs,
    _list_data,
    _post_map_to_self_id,
    _pre_map_translation,
    _split_common_objs,
    parse_jsonld_id,
    purge_orphans,
)
from events.models import Event, Image, Keyword, Place
from events.tests.factories import (
    DataSourceFactory,
    EventFactory,
    KeywordFactory,
    OrganizationFactory,
    PlaceFactory,
)


class BaseDataFactory(factory.DictFactory):
    id = factory.Sequence(lambda n: f"origin:{n}")
    data_source = "origin_ds"

    class Meta:
        abstract = True


class EventDataFactory(BaseDataFactory):
    super_event = None
    super_event_type = None
    publisher = None


def test_parse_jsonld_id():
    assert ["tprek:8100", "espoo:asdfasdf"] == (
        [
            parse_jsonld_id(
                {
                    "@id": "https://api.espoo.localhost/linkedevents/v1/place/tprek:8100/",
                }
            ),
            parse_jsonld_id(
                {
                    "@id": "https://api.espoo.localhost/linkedevents/v1/place/espoo:asdfasdf/",
                }
            ),
        ]
    )


@pytest.fixture
def sleep(monkeypatch):
    class Sleep:
        call_count = 0

        def sleep(self, t):
            self.call_count += 1

    sleep_instance = Sleep()

    monkeypatch.setattr("time.sleep", sleep_instance.sleep)
    return sleep_instance


def test_get_data(requests_mock):
    url = "http://localhost"
    data = {"hello": "world"}
    mock = requests_mock.get(url, json=data)
    assert data == _get_data(url)
    assert mock.call_count == 1


def test_get_max_retries(sleep, settings):
    def build_response(status_code):
        response = HTTPResponse(Mock())
        response.msg = HTTPMessage()
        response.msg["content-length"] = "0"
        response.fp = io.BytesIO()
        response.length = 0
        response.status = status_code
        response.chunked = False
        return response

    # Can't use requests_mock here
    url = "http://localhost:8000/"

    with patch(
        "urllib3.connectionpool.HTTPConnectionPool._make_request"
    ) as make_request_mock:
        make_request_mock.side_effect = [build_response(500)] * (
            settings.ESPOO_MAX_RETRIES + 1
        )

        with pytest.raises(EspooImporterError) as error:
            _get_data(url)

        assert "Exceeded max retries" in str(error.value)


def test_list_data(requests_mock, sleep):
    url = "http://localhost/"
    mock = requests_mock.get(
        url,
        [
            {"json": {"meta": {"next": url}, "data": [{"id": 1}, {"id": 2}]}},
            {"json": {"meta": {"next": url}, "data": [{"id": 3}, {"id": 4}]}},
            {"json": {"meta": {"next": None}, "data": [{"id": 5}]}},
        ],
    )
    response = _list_data(url)
    response_ids = [item["id"] for item in response]
    assert response_ids == [1, 2, 3, 4, 5]
    assert mock.call_count == 3
    assert sleep.call_count == 2


def test_list_max_pages(requests_mock, sleep, settings):
    url = "http://localhost/"
    mock = requests_mock.get(url, json={"meta": {"next": url}, "data": []})
    with pytest.raises(EspooImporterError):
        _list_data(url)
    assert mock.call_count == settings.ESPOO_MAX_PAGES


def test_get_origin_objs(requests_mock, sleep):
    requests_mock.get("http://localhost/model/ds:id1/", json={"id": "ds:id1"})
    requests_mock.get("http://localhost/model/ds:id2/", json={"id": "ds:id2"})

    objs = _get_origin_objs("http://localhost/model/", ["ds:id1", "ds:id2"])
    assert objs == [{"id": "ds:id1"}, {"id": "ds:id2"}]


@pytest.mark.django_db
def test_import_origin_objs():
    importer_ds = DataSourceFactory(id="importer_ds")
    imported_org = OrganizationFactory(
        data_source=importer_ds, origin_id="imported_org_id"
    )
    imported_unused_org = OrganizationFactory(
        data_source=importer_ds, origin_id="imported_unused_org_id"
    )

    origin_data = [
        {"id": imported_org.origin_id, "data_source": "origin_ds"},
        {"id": "new_org_id", "data_source": "origin_ds"},
    ]

    instance_map, synch = _import_origin_objs(
        Organization, importer_ds, [], origin_data
    )
    synch.finish()
    assert imported_org.origin_id in instance_map
    assert "new_org_id" in instance_map
    assert Organization.objects.filter(data_source=importer_ds).count() == 2
    with pytest.raises(Organization.DoesNotExist):
        Organization.objects.get(id=imported_unused_org.id)


@pytest.mark.django_db
def test_import_origin_objs_with_super_event():
    common_ds = DataSourceFactory(id="common_ds")
    common_org = OrganizationFactory(id="common_org", data_source=common_ds)
    super_event_data = EventDataFactory(publisher=common_org.id)
    super_event_jsonld = {"@id": f"https://localhost/{super_event_data['id']}/"}
    event_data = EventDataFactory(
        super_event=super_event_jsonld,
        super_event_type=Event.SuperEventType.UMBRELLA,
        publisher=common_org.id,
    )
    event_jsonld = {"@id": f"https://localhost/{event_data['id']}/"}
    recurring_event1_data = EventDataFactory(
        super_event=event_jsonld,
        super_event_type=Event.SuperEventType.RECURRING,
        publisher=common_org.id,
    )
    recurring_event2_data = EventDataFactory(
        super_event=event_jsonld,
        super_event_type=Event.SuperEventType.RECURRING,
        publisher=common_org.id,
    )

    # Setup data into non-hierarchical order
    origin_data = [
        recurring_event1_data,
        super_event_data,
        event_data,
        recurring_event2_data,
    ]

    importer_ds = DataSourceFactory(id="importer_ds")
    instance_map, synch = _import_origin_objs(
        Event,
        importer_ds,
        [],
        origin_data,
        copy_fields=["super_event_type"],
        pre_field_mappers={
            "publisher": _build_pre_map_to_id({common_org.id: common_org.id}),
        },
        post_field_mappers={
            "super_event": _post_map_to_self_id,
        },
    )
    synch.finish()

    assert len(instance_map) == 4

    super_event = Event.objects.get(origin_id=super_event_data["id"])
    event = Event.objects.get(origin_id=event_data["id"])
    recurring_event1 = Event.objects.get(origin_id=recurring_event1_data["id"])
    recurring_event2 = Event.objects.get(origin_id=recurring_event2_data["id"])

    assert super_event.super_event is None
    assert event.super_event == super_event
    assert recurring_event1.super_event == event
    assert recurring_event2.super_event == event

    assert super_event.super_event_type is None
    assert event.super_event_type == Event.SuperEventType.UMBRELLA
    assert recurring_event1.super_event_type == Event.SuperEventType.RECURRING
    assert recurring_event2.super_event_type == Event.SuperEventType.RECURRING


@pytest.mark.django_db
def test_split_common_objs():
    common_ds = DataSourceFactory(id="common_ds")
    importer_ds = DataSourceFactory(id="importer_ds")
    common_org = OrganizationFactory(data_source=common_ds)
    imported_org = OrganizationFactory(
        data_source=importer_ds, origin_id="imported_org_id"
    )

    origin_data = [
        {"id": common_org.id},
        {"id": imported_org.origin_id, "data_source": "origin_ds"},
        {"id": "new_org_id", "data_source": "origin_ds"},
    ]

    common_objs, origin_objs = _split_common_objs(
        Organization, importer_ds, origin_data
    )
    assert [common_org.id] == [i.id for i in common_objs]
    assert [imported_org.origin_id, "new_org_id"] == [
        origin_obj["id"] for origin_obj in origin_objs
    ]


def org_mock_data(_id: str):
    return {
        "id": _id,
        "name": Faker().bs(),
        "data_source": "espoo",
    }


def event_mock_data(
    _id,
    publisher,
    location,
    keywords=None,
    audience=None,
    offers=None,
    external_links=None,
    start_time=None,
    end_time=None,
    **kwargs,
):
    keywords = keywords or []
    audience = audience or []
    offers = offers or []
    external_links = external_links or []

    faker = Faker()
    end_time = end_time or faker.date_time(tzinfo=pytz.utc)
    return {
        "id": _id,
        "data_source": "espoo",
        "created_time": faker.iso8601(tzinfo=pytz.utc),
        "date_published": faker.iso8601(tzinfo=pytz.utc),
        "deleted": False,
        "end_time": end_time.isoformat(),
        "last_modified_time": faker.iso8601(tzinfo=pytz.utc),
        "start_time": (
            start_time.isoformat()
            if start_time
            else faker.iso8601(tzinfo=pytz.utc, end_datetime=end_time)
        ),
        "super_event_type": None,
        "name": {
            "fi": faker.bs(),
            "en": faker.bs(),
        },
        "description": None,
        "short_description": None,
        "info_url": None,
        "location_extra_info": None,
        "headline": None,
        "secondary_headline": None,
        "provider": None,
        "provider_contact_info": None,
        "event_status": "EventScheduled",
        "location": location,
        "publisher": publisher,
        "keywords": keywords,
        "audience": audience,
        "offers": offers,
        "external_links": external_links,
        "super_event": None,
        "images": [
            {
                "id": 11950,
                "license": "event_only",
                "created_time": "2024-01-31T10:54:22.360925Z",
                "last_modified_time": "2024-01-31T10:54:22.360956Z",
                "name": "Test Image",
                "url": "https://localhost/test_image.jpeg",
                "cropping": "72,0,625,554",
                "photographer_name": "",
                "alt_text": "lovely test picture",
                "data_source": "espoo",
                "publisher": "espoo:sito",
            }
        ],
        **kwargs,
    }


def keyword_mock_data(_id: str, publisher: str):
    return {
        "id": _id,
        "publisher": publisher,
        "name": {"fi": Faker().word()},
        "data_source": "espoo",
    }


def place_mock_data(_id: str, publisher: str):
    return {
        "id": _id,
        "publisher": publisher,
        "name": {"fi": Faker().word()},
        "data_source": "espoo",
    }


def mock_org_list_response(requests_mock, pks=(1, 2, 3)):
    requests_mock.get(
        f"{django_settings.ESPOO_API_URL}v1/organization/",
        json={
            "meta": {"count": len(pks), "next": None, "previous": None},
            "data": [org_mock_data(pk) for pk in pks],
        },
    )


@pytest.mark.django_db
def test_importer(settings, requests_mock, sleep, api_client):
    settings.ESPOO_API_URL = "http://localhost/"
    settings.ESPOO_API_EVENT_QUERY_PARAMS = {"test": 1}
    org1 = org_mock_data("test_org_1")
    org2 = org_mock_data("test_org_2")
    org3 = org_mock_data("test_org_3")

    kw1_data = keyword_mock_data("espoo:kw1", org1["id"])
    audience_kw_data = keyword_mock_data("espoo:audience_kw", org1["id"])
    place1_data = place_mock_data("espoo:place1", org1["id"])

    common_ds = DataSourceFactory(id="common")
    common_kw1 = KeywordFactory(data_source=common_ds)
    common_kw2 = KeywordFactory(data_source=common_ds)
    common_place1 = PlaceFactory(data_source=common_ds)

    common_kw1_data = keyword_mock_data(common_kw1.id, org1["id"])
    common_kw2_data = keyword_mock_data(common_kw2.id, org1["id"])
    common_place1_data = keyword_mock_data(common_place1.id, org1["id"])

    end = timezone.now()
    start = end - timezone.timedelta(days=1)

    event1 = event_mock_data(
        "espoo:event1",
        org1["id"],
        place1_data,
        [common_kw1_data],
        [audience_kw_data],
        start_time=start,
        end_time=end,
    )
    event2 = event_mock_data(
        "espoo:event2",
        org1["id"],
        common_place1_data,
        [common_kw1_data, common_kw2_data],
        offers=[
            {
                "is_free": True,
                "price": None,
            },
            {
                "is_free": False,
                "price": 10,
            },
        ],
        start_time=start,
        end_time=end,
    )
    event3 = event_mock_data(
        "espoo:event3",
        org2["id"],
        common_place1_data,
        [kw1_data],
        external_links=[{"name": "Foo", "language": "fi", "link": "https://localhost"}],
        description={
            "en": '<h1>h1 tags should disappear</h1><p>Hello world! <a href="https://google.com">Google</a></p>'
        },
        start_time=start,
        end_time=end,
    )

    requests_mock.get(
        f"{settings.ESPOO_API_URL}v1/organization/",
        json={
            "meta": {"count": 3, "next": None, "previous": None},
            "data": [org1, org2, org3],
        },
    )

    event_data = {
        "meta": {"count": 3, "next": None, "previous": None},
        "data": [event1, event2, event3],
    }

    requests_mock.get(
        f"{settings.ESPOO_API_URL}v1/event/?include=keywords%2Caudience%2Clocation&test=1",
        json=event_data,
    )

    importer = EspooImporter({"force": False})
    importer.import_events()

    assert Event.objects.filter(data_source=importer.data_source).count() == 3
    assert Image.objects.filter(data_source=importer.data_source).count() == 1
    assert Keyword.objects.filter(data_source=importer.data_source).count() == 2
    assert Place.objects.filter(data_source=importer.data_source).count() == 1

    # If we drop event1 from the data, the importer should clean up place1 and audience_kw
    # since it's no longer used
    event_data["data"] = [
        event for event in event_data["data"] if event["id"] != event1["id"]
    ]
    importer = EspooImporter({"force": False})
    importer.import_events()

    assert Event.objects.filter(data_source=importer.data_source).count() == 2
    assert Image.objects.filter(data_source=importer.data_source).count() == 1
    assert Keyword.objects.filter(data_source=importer.data_source).count() == 1
    assert Place.objects.filter(data_source=importer.data_source).count() == 0

    # Check that offers is set on event2
    event2 = Event.objects.get(origin_id=event2["id"])
    assert event2.offers.count() == 2

    # Check that external links is set on event3
    event3 = Event.objects.get(origin_id=event3["id"])
    assert event3.external_links.count() == 1

    # Check that link text matches
    assert event3.external_links.first().link == "https://localhost"

    assert (
        event3.description
        == 'h1 tags should disappear<p>Hello world! <a href="https://google.com">Google</a></p>'
    )

    # Finally lets make sure the importer can delete everything
    event_data["data"] = []
    importer = EspooImporter({"force": False})
    importer.import_events()

    assert Event.objects.filter(data_source=importer.data_source).count() == 0
    assert Image.objects.filter(data_source=importer.data_source).count() == 0
    assert Keyword.objects.filter(data_source=importer.data_source).count() == 0
    assert Place.objects.filter(data_source=importer.data_source).count() == 0
    assert Organization.objects.filter(data_source=importer.data_source).count() == 0


def test_purge_orphans_no_orphans():
    events_data = [
        {"id": "super", "super_event": None},
        {"id": "child", "super_event": {"@id": "https:/foobar/events/v1/event/super/"}},
        {
            "id": "grandchild",
            "super_event": {"@id": "https:/foobar/events/v1/event/child/"},
        },
    ]
    assert purge_orphans(events_data) == events_data


@pytest.mark.django_db
def test_importer_keeps_older_than_event_start_days_before(
    settings, requests_mock, sleep, api_client
):
    settings.ESPOO_API_URL = "http://localhost/"
    settings.ESPOO_API_EVENT_QUERY_PARAMS = {"test": 1}
    data_source = DataSourceFactory(id="espoo_le", name="Espoo Linkedevents")
    org = OrganizationFactory(
        id="test_org", data_source_id=data_source.id, origin_id="test_org"
    )
    place = PlaceFactory(
        id="espoo_le:place1", publisher_id=org.id, data_source_id=data_source.id
    )
    place_data = place_mock_data(place.id, org.id)
    now = timezone.now()
    wayback = now - timezone.timedelta(
        days=settings.ESPOO_API_EVENT_START_DAYS_BACK + 7
    )

    new_event = event_mock_data(
        "espoo_le:fresh",
        org.id,
        place_data,
        start_time=now,
        end_time=now + timezone.timedelta(days=1),
    )

    older_event = EventFactory(
        id="espoo_le:sour",
        publisher_id=org.id,
        data_source_id=data_source.id,
        location_id=place.id,
        start_time=wayback,
        end_time=wayback + timezone.timedelta(days=1),
    )

    requests_mock.get(
        f"{settings.ESPOO_API_URL}v1/organization/",
        json={
            "meta": {"count": 1, "next": None, "previous": None},
            "data": [org_mock_data(org.id)],
        },
    )

    event_data = {
        "meta": {"count": 2, "next": None, "previous": None},
        "data": [new_event],
    }

    requests_mock.get(
        f"{settings.ESPOO_API_URL}v1/event/?include=keywords%2Caudience%2Clocation&test=1",
        json=event_data,
    )

    importer = EspooImporter({"force": False})
    importer.import_events()

    # Test old event should stay in the database.
    assert Event.objects.filter(id=older_event.id).exists()
    assert Event.objects.filter(origin_id=new_event["id"]).exists()


def test_purge_orphans():
    events_data = [
        {"id": "unrelated", "super_event": None},
        {"id": "child", "super_event": {"@id": "https:/foobar/events/v1/event/super/"}},
        {
            "id": "grandchild",
            "super_event": {"@id": "https:/foobar/events/v1/event/child/"},
        },
    ]
    assert purge_orphans(events_data) == [
        {"id": "unrelated", "super_event": None},
    ]


@pytest.mark.parametrize(
    "field_name, field_data, data, expected_result",
    [
        # Single language
        ("name", {"en": "Event"}, {}, {"name_en": "Event"}),
        # Multiple languages
        (
            "name",
            {"en": "Event", "fi": "Tapahtuma"},
            {},
            {"name_en": "Event", "name_fi": "Tapahtuma"},
        ),
        # No translations
        ("name", None, {}, {}),
        # Unknown language
        (
            "name",
            {
                "en": "Event",
                "fi": "Tapahtuma",
                "iä": "Ph’nglui mglw’nafh Cthulhu R’lyeh wgah’nagl fhtagn",
            },
            {},
            {"name_en": "Event", "name_fi": "Tapahtuma"},
        ),
        # Existing data
        (
            "name",
            {"en": "Event"},
            {"foo": "bar"},
            {"foo": "bar", "name_en": "Event"},
        ),
    ],
)
def test_translation_field_mapper(
    settings, field_name, field_data, data, expected_result
):
    settings.LANGUAGES = [("en", "English"), ("fi", "Finnish")]
    result = _pre_map_translation(field_name, field_data, data)
    assert result == expected_result


@pytest.mark.django_db
def test__import_obj(settings):
    settings.LANGUAGES = [("en", "English"), ("fi", "Finnish")]
    settings.BLEACH_ALLOWED_TAGS = ["p"]
    data_source = DataSourceFactory(id="origin_ds")
    publisher = OrganizationFactory(data_source=data_source, origin_id="origin:org1")

    obj_data = {
        "id": "org1:event1",
        "data_source": "origin_ds",
        "publisher": publisher.origin_id,
        "name": "Event",
        "description": {"en": "<p><b>Description</b></p>"},
    }
    copy_fields = ["name"]
    pre_field_mappers = {
        # NOTE: The publisher pre-mapper is required, otherwise this won't work at all.
        "publisher": _build_pre_map_to_id({publisher.origin_id: publisher.id}),
        "description": _pre_map_translation,
    }

    instance = _import_origin_obj(
        obj_data, Event, data_source, copy_fields, pre_field_mappers
    )

    assert instance.name == "Event"
    assert instance.publisher == publisher
    assert instance.description == "<p>Description</p>"
