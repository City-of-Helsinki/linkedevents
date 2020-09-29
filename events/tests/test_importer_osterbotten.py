import pytest
import pytz
import dateutil.parser

from events.importer.osterbotten import OsterbottenImporter
from unittest.mock import MagicMock
from lxml import etree
from urllib.parse import urlparse, parse_qs

from .utils import get
from .utils import versioned_reverse as reverse


# === util methods ===


def get_event(api_client, id):
    detail_url = reverse('event-detail', version='v1', kwargs={'pk': id, }) + "?include=location,keywords"
    response = get(api_client, detail_url, data=None)
    return response.data


def assert_imported_osterbotten_event(locale, api_event, osterbotten_event):
    timezone = pytz.timezone('Europe/Helsinki')

    assert get_osterbotten_event_id(osterbotten_event) == api_event["id"]
    assert dateutil.parser.parse(osterbotten_event.xpath('Start')[0].text).astimezone(
        timezone) == dateutil.parser.parse(api_event["start_time"])
    assert dateutil.parser.parse(osterbotten_event.xpath('End')[0].text).astimezone(
        timezone) == dateutil.parser.parse(api_event["end_time"])

    assert osterbotten_event.xpath('Link')[0].text == api_event["info_url"][locale]
    assert osterbotten_event.xpath('Title')[0].text == api_event["name"][locale]
    assert osterbotten_event.xpath('EventText')[0].text == api_event["description"][locale]
    assert osterbotten_event.xpath('EventTextShort')[0].text == api_event["short_description"][locale]

    assert osterbotten_event.xpath('Place')[0].text == api_event["location"]["name"][locale]
    assert osterbotten_event.xpath('PostalOffice')[0].text == api_event["location"]["address_locality"][locale]
    assert osterbotten_event.xpath('PostalAddress')[0].text == api_event["location"]["street_address"][locale]
    assert osterbotten_event.xpath('PostalCode')[0].text == api_event["location"]["postal_code"]

    is_free = osterbotten_event.xpath('PriceType')[0].text == "Free"
    assert is_free == api_event["offers"][0]["is_free"]
    assert osterbotten_event.xpath('PriceHidden')[0].text == api_event["offers"][0]["price"][locale]
    assert osterbotten_event.xpath('PriceText')[0].text == api_event["offers"][0]["description"][locale]

    categories = osterbotten_event.xpath('Categories')[0]
    for category in categories:
        categoryId = category.xpath('ID')[0].text
        categoryText = category.xpath('Name')[0].text
        keywordId = "osterbotten:category_{}".format(categoryId)
        api_keyword = next(keyword for keyword in api_event["keywords"] if keyword["id"] == keywordId)
        assert categoryText == api_keyword["name"][locale]

    targetGroups = osterbotten_event.xpath('TargetGroups')[0]
    for targetGroup in targetGroups:
        targetGroupId = targetGroup.xpath('ID')[0].text
        targetGroupText = targetGroup.xpath('Name')[0].text
        keywordId = "osterbotten:target_{}".format(targetGroupId)

        api_keyword = next(keyword for keyword in api_event["keywords"] if keyword["id"] == keywordId)
        assert targetGroupText == api_keyword["name"][locale]


def get_osterbotten_event_id(osterbotten_event):
    return "osterbotten:{}".format(osterbotten_event.xpath('ID')[0].text)


def read_osterbotten_event(index, locale):
    return open("events/tests/static/osterbotten/event_{}_{}.xml".format(index + 1, locale), "r").read()


@pytest.fixture
def osterbotten_event_1_fi():
    return etree.fromstring(read_osterbotten_event(0, 'fi'))


@pytest.fixture
def osterbotten_event_2_fi():
    return etree.fromstring(read_osterbotten_event(1, 'fi'))


def mock_items_1_from_url(url):
    query = parse_qs(urlparse(url).query)
    start = query.get("Start")[0]
    locale = query.get("Locale")[0]

    if start == "0":
        if locale == "fi_FI":
            events = [read_osterbotten_event(0, "fi")]
        elif locale == "sv_SE":
            events = [read_osterbotten_event(0, "sv")]

    events_template = open("events/tests/static/osterbotten/events.xml", "r").read()

    return etree.fromstring(events_template.replace("___EVENTS___", ' '.join(map(str, events)))).xpath('Events/Event')


def mock_items_2_from_url(url):
    query = parse_qs(urlparse(url).query)
    start = query.get("Start")[0]
    locale = query.get("Locale")[0]
    events = []

    if start == "0":
        if locale == "fi_FI":
            events = [read_osterbotten_event(0, "fi"), read_osterbotten_event(1, "fi")]
        elif locale == "sv_SE":
            events = [read_osterbotten_event(0, "sv")]

    events_template = open("events/tests/static/osterbotten/events.xml", "r").read()
    return etree.fromstring(events_template.replace("___EVENTS___", ' '.join(map(str, events)))).xpath('Events/Event')


def mock_municipalities_from_url(url):
    response_file = open("events/tests/static/osterbotten/municipalities.xml", "r")
    return etree.fromstring(response_file.read()).xpath('Municipalities/Municipality')


# === tests ===


@pytest.mark.django_db
def test_import_osterbotten_events(api_client, osterbotten_event_1_fi, osterbotten_event_2_fi):
    importer = OsterbottenImporter({'verbosity': True, 'cached': False})
    importer.setup()
    importer.items_from_url = MagicMock(side_effect=mock_items_2_from_url)
    importer.municipalities_from_url = MagicMock(side_effect=mock_municipalities_from_url)
    importer.import_events()

    event_1_id = get_osterbotten_event_id(osterbotten_event_1_fi)
    event_2_id = get_osterbotten_event_id(osterbotten_event_2_fi)
    assert_imported_osterbotten_event("fi", get_event(api_client, event_1_id), osterbotten_event_1_fi)
    assert_imported_osterbotten_event("fi", get_event(api_client, event_2_id), osterbotten_event_2_fi)
