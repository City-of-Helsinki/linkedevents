from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from events.api import EventFilter
from events.models import Event
from events.tests.factories import EventFactory, KeywordFactory, PlaceFactory
from events.tests.test_event_get import get_list
from events.tests.utils import create_events_for_weekdays, create_super_event


@pytest.mark.django_db
def test_get_event_list_hide_recurring_children_true():
    event_1 = EventFactory()
    event_2 = EventFactory(data_source=event_1.data_source)
    super_1 = create_super_event([event_1, event_2], event_1.data_source)
    filter_set = EventFilter()

    result = filter_set.filter_hide_recurring_children(
        Event.objects.all(), "hide_recurring_children", True
    )

    assert result.count() == 1
    assert super_1 in result


@pytest.mark.django_db
def test_get_event_list_hide_recurring_children_false():
    event_1 = EventFactory()
    event_2 = EventFactory(data_source=event_1.data_source)
    super_1 = create_super_event([event_1, event_2], event_1.data_source)
    filter_set = EventFilter()

    result = filter_set.filter_hide_recurring_children(
        Event.objects.all(), "hide_recurring_children", False
    )

    assert result.count() == 3
    assert super_1 in result
    assert event_1 in result
    assert event_2 in result


def test_filter_full_text_wrong_language():
    request = Mock()
    request.query_params = {"x_full_text_language": "unknown"}
    filter_set = EventFilter(request=request)
    with pytest.raises(ValidationError):
        filter_set.filter_x_full_text(None, "x_full_text", "something")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "language,query_event,query_place,query_keyword",
    [
        ("fi", "Testitapahtuma", "Testipaikka", "Testiavainsana"),
        ("en", "Test event", "Test place", "Test keyword"),
        ("sv", "Testhändelse", "Testplats", "Testnyckelord"),
        ("ru", "Тестовое событие", "Тестовый участок", "Тестовое ключевое слово"),
        ("ar", "حدث اختباري", "مكان الاختبار", "اختبار الكلمة الرئيسية"),
        ("zh_hans", "测试事件", "考试地点", "测试关键字"),
    ],
)
def test_get_event_list_full_text(language, query_event, query_place, query_keyword):
    place_fi = PlaceFactory(
        name_fi="Testipaikka", name_en="Something else", name_sv="Something else"
    )
    place_en = PlaceFactory(
        name_en="Test place", name_fi="Something else", name_sv="Something else"
    )
    place_sv = PlaceFactory(
        name_sv="Testplats", name_en="Something else", name_fi="Something else"
    )
    place_zh_hans = PlaceFactory(
        name_zh_hans="考试地点", name_en="Something else", name_fi="Something else"
    )
    place_ru = PlaceFactory(
        name_ru="Тестовый участок", name_en="Something else", name_fi="Something else"
    )
    place_ar = PlaceFactory(
        name_ar="مكان الاختبار", name_en="Something else", name_fi="Something else"
    )
    kw_fi = KeywordFactory(
        name_fi="Testiavainsana", name_en="Something else", name_sv="Something else"
    )
    kw_en = KeywordFactory(
        name_en="Test keyword", name_fi="Something else", name_sv="Something else"
    )
    kw_sv = KeywordFactory(
        name_sv="Testnyckelord", name_en="Something else", name_fi="Something else"
    )
    kw_zh_hans = KeywordFactory(
        name_zh_hans="测试关键字", name_en="Something else", name_fi="Something else"
    )
    kw_ru = KeywordFactory(
        name_ru="Тестовое ключевое слово",
        name_en="Something else",
        name_fi="Something else",
    )
    kw_ar = KeywordFactory(
        name_ar="اختبار الكلمة الرئيسية",
        name_en="Something else",
        name_fi="Something else",
    )
    event_fi = EventFactory(
        id="test:fi",
        name_fi="Testitapahtuma",
        name_en="Something else",
        name_sv="Something else",
        location=place_fi,
    )
    event_en = EventFactory(
        id="test:en",
        name_en="Test event",
        name_fi="Something else",
        name_sv="Something else",
        location=place_en,
    )
    event_sv = EventFactory(
        id="test:sv",
        name_sv="Testhändelse",
        name_en="Something else",
        name_fi="Something else",
        location=place_sv,
    )
    event_ru = EventFactory(
        id="test:ru",
        name_ru="Тестовое событие",
        name_en="Something else",
        name_fi="Something else",
        location=place_ru,
    )
    event_ar = EventFactory(
        id="test:ar",
        name_ar="حدث اختباري",
        name_en="Something else",
        name_fi="Something else",
        location=place_ar,
    )
    event_zh_hans = EventFactory(
        id="test:zh_hans",
        name_zh_hans="测试事件",
        name_en="Something else",
        name_fi="Something else",
        location=place_zh_hans,
    )

    event_fi.keywords.set([kw_fi])
    event_en.keywords.set([kw_en])
    event_sv.keywords.set([kw_sv])
    event_ru.keywords.set([kw_ru])
    event_ar.keywords.set([kw_ar])
    event_zh_hans.keywords.set([kw_zh_hans])

    call_command("rebuild_event_search_index")

    request = Mock()
    request.query_params = {"x_full_text_language": language}

    filter_set = EventFilter(request=request)

    def do_filter(query):
        return filter_set.filter_x_full_text(
            Event.objects.all(), "x_full_text", f"{query}"
        )

    result = do_filter(query_event)
    assert result.count() == 1
    assert result[0].id == f"test:{language}"

    result = do_filter(query_place)
    assert result.count() == 1
    assert result[0].id == f"test:{language}"

    result = do_filter(query_keyword)
    assert result.count() == 1
    assert result[0].id == f"test:{language}"


@pytest.mark.django_db
def test_get_event_search_full_text():
    place = PlaceFactory(name_fi="Kissakuja")
    kw = KeywordFactory(name_fi="Avainsanatehdas")
    audience = KeywordFactory(name_fi="Kirjastokortti")
    event = EventFactory(
        id="test:fi",
        name_fi="Oodi keväälle - Matkallelähtökonsertti 2025",
        short_description_fi="Kauppakorkeakoulun Ylioppilaskunnan Laulajat suuntaa vapun jälkeen "
        "Irlantiin Corkin kansainväliselle kuorofestivaalille",
        description_fi="Konsertin huippukohtia ovat muun muassa Säde Bartlingilta "
        "tilaamamme kansansävelmäsovituksen Metsän puita tuuli "
        "tuudittaa kantaesitys 6-9-vuotiaille",
        location=place,
    )

    event.keywords.set([kw])
    event.audience.set([audience])

    call_command("rebuild_event_search_index")

    request = Mock()
    request.query_params = {"x_full_text_language": "fi"}

    filter_set = EventFilter(request=request)

    def do_filter(query):
        return filter_set.filter_x_full_text(
            Event.objects.all(), "x_full_text", f"{query}"
        )

    result = do_filter("kissoja")
    assert result.count() == 1
    assert result[0].id == "test:fi"

    result = do_filter("keväälle 2")
    assert result.count() == 0

    result = do_filter("keväälle 20")
    assert result.count() == 0

    result = do_filter("keväälle 202")
    assert result.count() == 0

    result = do_filter("keväälle 2024")
    assert result.count() == 0

    result = do_filter("keväälle 2025")
    assert result.count() == 1
    assert result[0].id == "test:fi"

    result = do_filter("6-9-vuotiaille")
    assert result.count() == 1
    assert result[0].id == "test:fi"

    result = do_filter("yhdeksän-vuotiaille")
    assert result.count() == 1
    assert result[0].id == "test:fi"

    result = do_filter("tehtaassa")
    assert result.count() == 1
    assert result[0].id == "test:fi"

    result = do_filter("Säde")
    assert result.count() == 1
    assert result[0].id == "test:fi"

    result = do_filter("kansainvälisellä kuorofestivaalilla")
    assert result.count() == 1
    assert result[0].id == "test:fi"

    result = do_filter("konserttina...")
    assert result.count() == 1
    assert result[0].id == "test:fi"

    result = do_filter("kirjastokortti")
    assert result.count() == 1
    assert result[0].id == "test:fi"


@pytest.mark.django_db
def test_get_event_search_full_text_special_characters():
    place = PlaceFactory(name_fi="Kissakuja")
    kw = KeywordFactory(name_fi="Avainsanatehdas")
    event = EventFactory(
        id="test:fi",
        name_fi="Oodi keväälle - Matkallelähtökonsertti",
        short_description_fi="Kauppakorkeakoulun Ylioppilaskunnan Laulajat suuntaa vapun jälkeen "
        "Irlantiin Corkin kansainväliselle kuorofestivaalille",
        description_fi="Konsertin huippukohtia ovat muun muassa Säde Bartlingilta "
        "tilaamamme kansansävelmäsovituksen Metsän puita tuuli "
        "tuudittaa kantaesitys",
        location=place,
    )

    event.keywords.set([kw])

    call_command("rebuild_event_search_index")

    request = Mock()
    request.query_params = {"x_full_text_language": "fi"}

    filter_set = EventFilter(request=request)

    def do_filter(query):
        return filter_set.filter_x_full_text(
            Event.objects.all(), "x_full_text", f"{query}"
        )

    result = do_filter("kevääksi .,:;()[]{}*'\"^¨+=-_<>")
    assert result.count() == 1
    assert result[0].id == "test:fi"


@pytest.mark.django_db
def test_get_event_search_full_text_with_embedded_html():
    place = PlaceFactory(
        name_fi="Mannerheimintie 7",
        name_sv="Mannerheimvägen 7",
        name_en="Mannerheimintie 7",
    )
    kw_1 = KeywordFactory(
        name_fi="Opastukset ja kurssit",
        name_sv="Undervisning och kurser",
        name_en="Training and courses",
    )
    kw_2 = KeywordFactory(name_fi="Tapahtumat", name_en="Events", name_sv="Evenemang")
    event = EventFactory(
        id="test:fi",
        name_fi="Tietotekniikkaopastusta senioreille",
        short_description_fi="Tietotekniikkaopastus senioreille Entressen kirjastossa",
        description_fi="<h2>Haluaisitko apua ja neuvoja tietokoneen, internetin tai sähköpostin peruskäyttöön?</h2>"
        "<h3></h3><p>Maksutonta tietotekniikkaopastuksia on tarjolla Entressen kirjastossa "
        "ajanvarauksella <strong>torstaisin </strong><b>11.1. - 16.5. </b>"
        "<strong>2024 </strong><b>kello 11 - 13 . </b></p>"
        "<p>Opastus tapahtuu asiakkaan omalla kannettavalla tietokoneella, mobiililaitteella "
        "tai kirjaston asiakaskoneella. Opastuksissa käydään läpi tietokoneen käytön ja "
        "internetin palveluiden perusteita. Opastus kestää yhden tunnin. "
        "Opastusaika varataan etukäteen joko puhelimitse numerossa 09 1234 5678 "
        "tai paikan päällä kirjastossa. Asiakkaalla voi olla opastukseen vain yksi varaus "
        "kerrallaan.</p><p>Ry on tieto- ja viestintätekniikasta sekä vapaaehtoistoiminnasta "
        "kiinnostuneiden eläkeläisten yhdistys. "
        'Yhdistyksen kotisivu: <a href="https://www.random.fi/">Ry</a>.</p>',
        location=place,
    )

    event.keywords.set([kw_1, kw_2])

    call_command("rebuild_event_search_index")

    request = Mock()
    request.query_params = {"x_full_text_language": "fi"}

    filter_set = EventFilter(request=request)

    def do_filter(query):
        return filter_set.filter_x_full_text(
            Event.objects.all(), "x_full_text", f"{query}"
        )

    result = do_filter("tapahtuma,eläkeläisille")
    assert result.count() == 1
    assert result[0].id == "test:fi"


@pytest.mark.django_db
@pytest.mark.parametrize("ongoing", [True, False])
def test_get_event_list_ongoing(ongoing):
    now = timezone.now()
    event_end_before = EventFactory(end_time=now - timedelta(hours=1))
    event_end_after = EventFactory(end_time=now + timedelta(hours=1))

    filter_set = EventFilter()

    qs = filter_set.filter_x_ongoing(Event.objects.all(), "x_ongoing", ongoing)

    assert qs.count() == 1
    if ongoing:
        assert event_end_after in qs
    else:
        assert event_end_before in qs


@pytest.mark.django_db
def test_get_event_list_min_duration():
    EventFactory(start_time=timezone.now(), end_time=timezone.now())
    event_long = EventFactory(
        start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=1)
    )

    filter_set = EventFilter()

    qs = filter_set.filter_min_duration(Event.objects.all(), "min_duration", "1h")

    assert qs.count() == 1
    assert event_long in qs


@pytest.mark.django_db
def test_get_event_list_max_duration():
    event_short = EventFactory(start_time=timezone.now(), end_time=timezone.now())
    EventFactory(
        start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=1)
    )

    filter_set = EventFilter()

    qs = filter_set.filter_max_duration(Event.objects.all(), "max_duration", "1h")

    assert qs.count() == 1
    assert event_short in qs


@pytest.mark.django_db
def test_get_event_list_hide_super_event_true():
    event_1 = EventFactory()
    event_2 = EventFactory(data_source=event_1.data_source)
    super_1 = create_super_event([event_1, event_2], event_1.data_source)
    filter_set = EventFilter()

    result = filter_set.filter_hide_super_event(
        Event.objects.all(), "hide_super_event", True
    )

    assert result.count() == 2
    assert event_1 in result
    assert event_2 in result
    assert super_1 not in result


@pytest.mark.django_db
def test_get_event_list_hide_super_event_false():
    event_1 = EventFactory()
    event_2 = EventFactory(data_source=event_1.data_source)
    super_1 = create_super_event([event_1, event_2], event_1.data_source)
    filter_set = EventFilter()

    result = filter_set.filter_hide_super_event(
        Event.objects.all(), "hide_super_event", False
    )

    assert result.count() == 3
    assert super_1 in result
    assert event_1 in result
    assert event_2 in result


@pytest.mark.django_db
@pytest.mark.parametrize("iso_weekday, expected_name", settings.ISO_WEEKDAYS)
def test_get_event_list_filter_weekdays(api_client, iso_weekday, expected_name):
    create_events_for_weekdays()
    resp = get_list(api_client, query_string=f"weekday={iso_weekday}")
    data = resp.data["data"]

    assert len(data) == 1
    assert data[0]["name"]["fi"] == expected_name.lower()
    assert parse_datetime(data[0]["start_time"]).isoweekday() == iso_weekday


@pytest.mark.django_db
def test_get_event_list_filter_multiple_weekdays(api_client):
    create_events_for_weekdays()
    EventFactory(
        name="everyday",
        start_time=timezone.datetime(2025, 3, 10, 12, tzinfo=timezone.utc),
        end_time=timezone.datetime(2025, 3, 16, 12, tzinfo=timezone.utc),
    )
    EventFactory(
        name="over weekender",
        start_time=timezone.datetime(2025, 3, 14, 12, tzinfo=timezone.utc),
        end_time=timezone.datetime(2025, 3, 18, 12, tzinfo=timezone.utc),
    )

    resp = get_list(api_client, query_string="weekday=1,2,3")
    data = sorted(resp.data["data"], key=lambda x: x["end_time"])

    assert len(data) == 5
    assert data[0]["name"]["fi"] == "monday"
    assert parse_datetime(data[0]["start_time"]).isoweekday() == 1
    assert data[1]["name"]["fi"] == "tuesday"
    assert parse_datetime(data[1]["start_time"]).isoweekday() == 2
    assert data[2]["name"]["fi"] == "wednesday"
    assert parse_datetime(data[2]["start_time"]).isoweekday() == 3
    assert data[3]["name"]["fi"] == "everyday"
    assert data[4]["name"]["fi"] == "over weekender"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "iso_weekday, count",
    [
        (1, 3),
        (2, 4),
        (3, 2),
        (4, 1),
        (5, 2),
        (6, 2),
        (7, 3),
    ],
)
def test_get_event_list_filter_weekdays_spans_over_weekend(
    api_client, iso_weekday, count
):
    create_events_for_weekdays()
    EventFactory(
        name="other tuesday event",
        start_time=timezone.datetime(2025, 3, 11, 12, tzinfo=timezone.utc),
        end_time=timezone.datetime(2025, 3, 11, 14, tzinfo=timezone.utc),
    )
    EventFactory(
        name="friday saturday sunday monday tuesday",
        start_time=timezone.datetime(2025, 3, 14, 12, tzinfo=timezone.utc),
        end_time=timezone.datetime(2025, 3, 18, 12, tzinfo=timezone.utc),
    )
    EventFactory(
        name="sunday monday tuesday wednesday",
        start_time=timezone.datetime(2025, 3, 16, 12, tzinfo=timezone.utc),
        end_time=timezone.datetime(2025, 3, 19, 12, tzinfo=timezone.utc),
    )

    resp = get_list(api_client, query_string=f"weekday={iso_weekday}")
    data = resp.data["data"]

    ids = {event["id"] for event in data}
    assert len(ids) == count
    assert all(
        [
            settings.ISO_WEEKDAYS[iso_weekday - 1][1].lower() in event["name"]["fi"]
            for event in data
        ]
    )


@pytest.mark.django_db
@pytest.mark.parametrize("iso_weekday, name", settings.ISO_WEEKDAYS)
def test_get_event_list_over_week_event(iso_weekday, name, api_client):
    EventFactory(
        name="long event",
        start_time=timezone.datetime(
            2025, 3, 12, 23, tzinfo=timezone.get_default_timezone()
        ),
        end_time=timezone.datetime(
            2025, 3, 18, 1, tzinfo=timezone.get_default_timezone()
        ),
    )

    resp = get_list(api_client, query_string=f"weekday={iso_weekday}")
    data = resp.data["data"]

    assert len(data) == 1
    assert data[0]["name"]["fi"] == "long event"


@pytest.mark.django_db
def test_get_event_list_hide_recurring_children_weekday_matches_sub_events(api_client):
    monday_event = EventFactory(start_time=datetime(2025, 1, 6))
    tuesday_event = EventFactory(
        data_source=monday_event.data_source, start_time=datetime(2025, 1, 7)
    )
    create_super_event([monday_event, tuesday_event], monday_event.data_source)

    thursday = timezone.datetime(2025, 3, 6, 12, tzinfo=timezone.utc)
    event_3 = EventFactory(start_time=thursday, end_time=thursday + timedelta(hours=1))
    super_of_thursday = create_super_event([event_3], event_3.data_source)

    resp = get_list(
        api_client,
        query_string="weekday=4&hide_recurring_children=true&hide_recurring_children_sub_events=true",
    )
    data = resp.data["data"]

    assert len(data) == 1
    assert data[0]["id"] == super_of_thursday.id


@pytest.mark.django_db
def test_get_event_list_hide_recurring_children_start_matches_sub_events(api_client):
    event_1 = EventFactory(start_time=datetime(2025, 1, 6))
    event_2 = EventFactory(start_time=datetime(2025, 1, 7))
    create_super_event([event_1, event_2], event_1.data_source)

    thursday = timezone.datetime(2025, 3, 6, 12, tzinfo=timezone.utc)
    event_3 = EventFactory(start_time=thursday, end_time=thursday + timedelta(hours=1))
    super_2 = create_super_event([event_3], event_3.data_source)

    resp = get_list(
        api_client,
        query_string="start=2025-03-06&hide_recurring_children=true&hide_recurring_children_sub_events=true",
    )
    data = resp.data["data"]

    assert len(data) == 1
    assert data[0]["id"] == super_2.id


@pytest.mark.django_db
def test_get_event_list_hide_recurring_children_publisher_match_sub_events_and_non_sub(
    api_client,
):
    event_1 = EventFactory()
    event_2 = EventFactory()
    super_1 = create_super_event([event_1, event_2], event_1.data_source)

    event_3 = EventFactory()
    create_super_event([event_3], event_3.data_source)
    event_4 = EventFactory(publisher=event_1.publisher)

    resp = get_list(
        api_client,
        query_string=f"publisher={event_1.publisher_id}&hide_recurring_children=true&hide_recurring_children_sub_events=true",
    )
    data = resp.data["data"]

    assert len(data) == 2
    event_ids = [event["id"] for event in data]
    assert super_1.id in event_ids
    assert event_4.id in event_ids
