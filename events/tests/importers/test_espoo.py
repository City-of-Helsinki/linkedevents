import io
from http.client import HTTPMessage, HTTPResponse
from unittest.mock import Mock, patch

import factory
import pytest
import pytz
from django.conf import settings
from django_orghierarchy.models import Organization
from faker import Faker

from events.importer.espoo import (
    _build_pre_map_to_id,
    _get_data,
    _get_origin_objs,
    _import_origin_objs,
    _list_data,
    _post_map_to_self_id,
    _split_common_objs,
    EspooImporter,
    EspooImporterError,
    parse_jsonld_id,
)
from events.models import Event, Keyword, Place
from events.tests.factories import (
    DataSourceFactory,
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


@pytest.mark.no_test_audit_log
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


@pytest.mark.no_test_audit_log
def test_get_data(requests_mock):
    url = "http://localhost"
    data = {"hello": "world"}
    mock = requests_mock.get(url, json=data)
    assert data == _get_data(url)
    assert mock.call_count == 1


@pytest.mark.no_test_audit_log
def test_get_max_retries(sleep):
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


@pytest.mark.no_test_audit_log
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


@pytest.mark.no_test_audit_log
def test_list_max_pages(requests_mock, sleep):
    url = "http://localhost/"
    mock = requests_mock.get(url, json={"meta": {"next": url}, "data": []})
    with pytest.raises(EspooImporterError):
        _list_data(url)
    assert mock.call_count == settings.ESPOO_MAX_PAGES


@pytest.mark.no_test_audit_log
def test_get_origin_objs(requests_mock, sleep):
    requests_mock.get("http://localhost/model/ds:id1/", json={"id": "ds:id1"})
    requests_mock.get("http://localhost/model/ds:id2/", json={"id": "ds:id2"})

    objs = _get_origin_objs("http://localhost/model/", ["ds:id1", "ds:id2"])
    assert objs == [{"id": "ds:id1"}, {"id": "ds:id2"}]


@pytest.mark.no_test_audit_log
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


@pytest.mark.no_test_audit_log
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


@pytest.mark.no_test_audit_log
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
):
    keywords = keywords or []
    audience = audience or []
    offers = offers or []
    external_links = external_links or []

    faker = Faker()
    end_time = faker.date_time(tzinfo=pytz.utc)
    return {
        "id": _id,
        "data_source": "espoo",
        "created_time": faker.iso8601(tzinfo=pytz.utc),
        "date_published": faker.iso8601(tzinfo=pytz.utc),
        "deleted": False,
        "end_time": end_time.isoformat(),
        "last_modified_time": faker.iso8601(tzinfo=pytz.utc),
        "start_time": faker.iso8601(tzinfo=pytz.utc, end_datetime=end_time),
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
        "images": [],
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
        f"{settings.ESPOO_API_URL}v1/organization/",
        json={
            "meta": {"count": len(pks), "next": None, "previous": None},
            "data": [org_mock_data(pk) for pk in pks],
        },
    )


@pytest.mark.no_test_audit_log
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

    event1 = event_mock_data(
        "espoo:event1", org1["id"], place1_data, [common_kw1_data], [audience_kw_data]
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
    )
    event3 = event_mock_data(
        "espoo:event3",
        org2["id"],
        common_place1_data,
        [kw1_data],
        external_links=[{"name": "Foo", "language": "fi", "link": "https://localhost"}],
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

    # Finally lets make sure the importer can delete everything
    event_data["data"] = []
    importer = EspooImporter({"force": False})
    importer.import_events()

    assert Event.objects.filter(data_source=importer.data_source).count() == 0
    assert Keyword.objects.filter(data_source=importer.data_source).count() == 0
    assert Place.objects.filter(data_source=importer.data_source).count() == 0
    assert Organization.objects.filter(data_source=importer.data_source).count() == 0
