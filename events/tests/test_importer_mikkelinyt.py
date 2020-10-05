import pytest
import pytz
import re

import dateutil.parser
from datetime import datetime, timedelta
from html.parser import HTMLParser
from events.importer.mikkelinyt import MikkeliNytImporter
from unittest.mock import MagicMock

from .utils import get
from .utils import versioned_reverse as reverse


# === util methods ===


def get_event(api_client, id):
    detail_url = reverse('event-detail', version='v1', kwargs={'pk': id, }) + "?include=location,keywords"
    response = get(api_client, detail_url, data=None)
    return response.data


def assert_imported_mikkelinyt_event(api_event, mikkelinyt_event):
    assert get_mikkelinyt_event_id(mikkelinyt_event) == api_event["id"]
    assert mikkelinyt_event["url"] == api_event["info_url"]["fi"]
    assert mikkelinyt_event["name"] == api_event["name"]["fi"]
    assert mikkelinyt_event["description"] == api_event["description"]["fi"]
    assert mikkelinyt_event["description"] == api_event["short_description"]["fi"]

    assert strip_html(mikkelinyt_event["city"]) == api_event["location"]["address_locality"]["fi"]
    assert strip_html(mikkelinyt_event["place"]) == api_event["location"]["name"]["fi"]
    assert strip_html(mikkelinyt_event["address"]) == api_event["location"]["street_address"]["fi"]
    assert strip_html(mikkelinyt_event["zip"]) == api_event["location"]["postal_code"]

    assert mikkelinyt_event["thumb"] == next(image for image in api_event["images"] if image["name"] == "thumb")["url"]
    assert mikkelinyt_event["image"] == next(image for image in api_event["images"] if image["name"] == "image")["url"]
    assert mikkelinyt_event["image_original"] == next(image for image in api_event["images"]
                                                      if image["name"] == "image_original")["url"]

    is_free = mikkelinyt_event["tickets"] == "ilmainen"
    assert is_free == api_event["offers"][0]["is_free"]
    assert mikkelinyt_event["tickets"] == api_event["offers"][0]["description"]["fi"]
    assert mikkelinyt_event["tickets_url"] == api_event["offers"][0]["info_url"]["fi"]

    for mikkelinyt_category in mikkelinyt_event["category"]:
        api_keyword = next(keyword for keyword in api_event["keywords"]
                           if keyword["id"] == 'mikkelinyt:{}'.format(mikkelinyt_category["id"]))
        assert mikkelinyt_category["name"] == api_keyword["name"]["fi"]

    assert_imported_time(mikkelinyt_event["start"], api_event["start_time"])
    assert_imported_time(mikkelinyt_event["end"], api_event["end_time"])


def assert_imported_time(mikkelinyt_event_time, api_event_time):
    timezone = pytz.timezone('Europe/Helsinki')
    mikkelinyt_event_time_parsed = datetime.strptime(mikkelinyt_event_time, '%Y-%m-%d %H:%M:%S').astimezone(timezone)
    api_event_time_parsed = dateutil.parser.parse(api_event_time)
    assert mikkelinyt_event_time_parsed == api_event_time_parsed


def strip_html(text):
    result = re.sub(r"\<.*?>", " ", text, 0, re.MULTILINE)
    result = HTMLParser().unescape(result)
    result = " ".join(result.split())
    return result.strip()


def get_mikkelinyt_event_id(mikkelinyt_event):
    return 'mikkelinyt:{}'.format(mikkelinyt_event["id"])


def get_mikkelinyt_formatted_time(datetime):
    return datetime.strftime('%Y-%m-%d %H:%M:%S')


@pytest.fixture
def mikkelinyt_event_1():
    return {
        "id": 123456,
        "url": "https://events.example.org/event/test-123456",
        "name": "Test event 123456",
        "description": "Event 123456 for testing",
        "niceDatetime": "2.1.2020 - 2.1.2021 klo 14:00 - 16:20",
        "start": get_mikkelinyt_formatted_time(datetime.now() + timedelta(hours=1)),
        "end": get_mikkelinyt_formatted_time(datetime.now() + timedelta(days=10)),
        "city": "<span class=\"City\">Example</span>",
        "place": "<span class=\"place\">Example place</span>",
        "address": "<span class=\"Address\">Example street 1</span>",
        "zip": "<span class=\"Zip\">12345</span>",
        "location": "<span class=\"place\">Example place</span>, <span class=\"Address\">Example street 1</span>, \
            <span class=\"Zip\">12345</span>, <span class=\"City\">Example</span>",
        "thumb": "https://events.example.org/uploads/events/480/ABC.jpg",
        "image": "https://events.example.org/uploads/events/1140/ABC.jpg",
        "image_original": "https://events.example.org/uploads/events/ABC.jpg",
        "tickets": "Tickets 150 €",
        "tickets_url": "https://www.example.org/event-url",
        "registration": "",
        "organizer": "Example Org",
        "category": [
            {
                "id": "1",
                "name": "Test"
            }
        ]
    }


@pytest.fixture
def mikkelinyt_event_2():
    return {
        "id": 223456,
        "url": "https://events.example.org/event/test-223456",
        "name": "Test event 223456",
        "description": "Event 223456 for testing\r\n<br />\r\n with linebreaks!",
        "niceDatetime": "2.1.2020 - 2.1.2020 klo 14:00 - 16:20",
        "start": get_mikkelinyt_formatted_time(datetime.now() + timedelta(hours=1)),
        "end": get_mikkelinyt_formatted_time(datetime.now() + timedelta(hours=2)),
        "city": "<span class=\"City\">Example</span>",
        "place": "<span class=\"place\">Example place</span>",
        "address": "<span class=\"Address\">Example street 1</span>",
        "zip": "<span class=\"Zip\">12345</span>",
        "location": "<span class=\"place\">Example place</span>, <span class=\"Address\">Example street 1</span>, \
            <span class=\"Zip\">12345</span>, <span class=\"City\">Example</span>",
        "thumb": "https://events.example.org/uploads/events/480/BBC.jpg",
        "image": "https://events.example.org/uploads/events/1140/BBC.jpg",
        "image_original": "https://events.example.org/uploads/events/BBC.jpg",
        "tickets": "ilmainen",
        "tickets_url": "https://www.example.org/event-2-url",
        "registration": "https://www.example.org/event-2-url/register",
        "organizer": "Example Org",
        "category": [
            {
                "id": "1",
                "name": "Test"
            }
        ]
    }


# === tests ===


@pytest.mark.django_db
def test_import_mikkelinyt_events(api_client, mikkelinyt_event_1, mikkelinyt_event_2):
    event_1_id = get_mikkelinyt_event_id(mikkelinyt_event_1)
    event_2_id = get_mikkelinyt_event_id(mikkelinyt_event_2)

    importer = MikkeliNytImporter({'verbosity': True, 'cached': False})
    importer.setup()
    importer.items_from_url = MagicMock(return_value=[mikkelinyt_event_1, mikkelinyt_event_2])
    importer.import_events()

    assert_imported_mikkelinyt_event(get_event(api_client, event_1_id), mikkelinyt_event_1)
    assert_imported_mikkelinyt_event(get_event(api_client, event_2_id), mikkelinyt_event_2)


@pytest.mark.django_db
def test_import_mikkelinyt_events_removed(api_client, mikkelinyt_event_1, mikkelinyt_event_2):
    event_1_id = get_mikkelinyt_event_id(mikkelinyt_event_1)
    event_2_id = get_mikkelinyt_event_id(mikkelinyt_event_2)

    importer1 = MikkeliNytImporter({'verbosity': True, 'cached': False})
    importer1.setup()
    importer1.items_from_url = MagicMock(return_value=[mikkelinyt_event_1, mikkelinyt_event_2])
    importer1.import_events()

    assert_imported_mikkelinyt_event(get_event(api_client, event_1_id), mikkelinyt_event_1)
    assert_imported_mikkelinyt_event(get_event(api_client, event_2_id), mikkelinyt_event_2)

    importer2 = MikkeliNytImporter({'verbosity': True, 'cached': False})
    importer2.items_from_url = MagicMock(return_value=[mikkelinyt_event_1])
    importer2.setup()
    importer2.import_events()

    assert_imported_mikkelinyt_event(get_event(api_client, event_1_id), mikkelinyt_event_1)
    event_2_response = api_client.get(reverse('event-detail', kwargs={'pk': event_2_id}))
    assert event_2_response.status_code == 410
