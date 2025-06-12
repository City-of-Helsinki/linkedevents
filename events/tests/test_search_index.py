import pytest
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from events.models import Event, EventSearchIndex
from events.search_index.utils import convert_numbers, extract_word_bases
from events.tests.factories import EventFactory, PlaceFactory


@pytest.mark.parametrize(
    "word, expected_result",
    [
        ("lentokone", {"lentää", "kone"}),
        ("lentokoneen", {"lentää", "kone"}),
        ("lentokoneita", {"lentää", "kone"}),
        ("päiväkoti", {"päivä", "koti"}),
        ("kissoja", {"kissa"}),
        ("saippuakivimittakaava", {"saippua", "kivi", "mitta", "kaava"}),
        ("kokonaisvaltainen", {"koko", "nainen", "kokonainen", "valta"}),
        ("ei ole olemassa", {"olla"}),
        ("ja hei huomenna ennen sitä sinä hyppäät yli riman", {"hypätä", "rima"}),
        (
            "<h1>Otsikko</h1> jälkeen tulee tekstiä ja<br>rivinvaihto",
            {"otsikko", "jälki", "tulla", "teksti", "rivi", "vaihto"},
        ),
    ],
)
def test_extract_word_bases(word, expected_result):
    result = extract_word_bases(word, set())
    assert result == expected_result


@pytest.mark.parametrize(
    "word, expected_result",
    [
        ("0", {"nolla", "0"}),
        ("1", {"yksi", "1"}),
        ("22", {"kaksikymmentäkaksi", "22"}),
        ("300", {"kolmesataa", "300"}),
        ("4000", {"neljätuhatta", "4000"}),
        ("Vuosi 2025", {"kaksituhatta kaksikymmentäviisi", "2025"}),
        (
            "Eka 123 toka 456",
            {"satakaksikymmentäkolme", "neljäsataaviisikymmentäkuusi", "123", "456"},
        ),
        (
            "Numero 1234567890",
            {
                "miljardi kaksisataakolmekymmentäneljämiljoonaa "
                "viisisataakuusikymmentäseitsemäntuhatta kahdeksansataayhdeksänkymmentä",
                "1234567890",
            },
        ),
    ],
)
def test_get_number_as_finnish_word(word, expected_result):
    result = convert_numbers(word)
    assert result == expected_result


@pytest.mark.django_db
def test_rebuild_search_index(event, place, keyword):
    keyword.name_fi = "tunnettu_avainsana"
    keyword.name_sv = "känd_nyckelord"
    keyword.name_en = "known_keyword"
    keyword.save()
    event.keywords.add(keyword)
    call_command("rebuild_event_search_index")
    assert EventSearchIndex.objects.all().count() == 1
    event_full_text = EventSearchIndex.objects.first()
    assert event_full_text.event == event
    assert event_full_text.place == place
    assert event_full_text.event_last_modified_time == event.last_modified_time
    assert event_full_text.place_last_modified_time == place.last_modified_time
    assert event_full_text.search_vector_fi is not None
    assert event_full_text.search_vector_sv is not None
    assert event_full_text.search_vector_en is not None
    assert event_full_text.search_vector_zh_hans is not None
    assert event_full_text.search_vector_ru is not None
    assert event_full_text.search_vector_ar is not None
    assert place.name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    assert place.name_sv[:4].lower() in str(event_full_text.search_vector_sv)
    assert place.name_en[:4].lower() in str(event_full_text.search_vector_en)
    assert event.name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    assert event.name_sv[:4].lower() in str(event_full_text.search_vector_sv)
    assert event.name_en[:4].lower() in str(event_full_text.search_vector_en)
    assert keyword.name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    assert keyword.name_sv[:4].lower() in str(event_full_text.search_vector_sv)
    assert keyword.name_en[:4].lower() in str(event_full_text.search_vector_en)


@pytest.mark.django_db
def test_rebuild_search_index_event_last_modified_time_null(event, place, keyword):
    Event.objects.filter(pk=event.pk).update(last_modified_time=None)
    event.refresh_from_db()
    assert event.last_modified_time is None
    call_command("rebuild_event_search_index")
    assert EventSearchIndex.objects.all().count() == 1
    event_full_text = EventSearchIndex.objects.first()
    assert event_full_text.event_last_modified_time is None


@pytest.mark.skipif(
    not settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED,
    reason="Event search signals disabled",
)
@pytest.mark.django_db
def test_auto_update_event_search_index_on_event_create(
    event, place, keyword, data_source
):
    event.keywords.add(keyword)
    event.save()
    assert EventSearchIndex.objects.all().count() == 1
    event_full_text = EventSearchIndex.objects.first()
    assert event_full_text.event == event
    assert event_full_text.place == place
    assert event_full_text.event_last_modified_time == event.last_modified_time
    assert event_full_text.place_last_modified_time == place.last_modified_time
    assert event_full_text.search_vector_fi is not None
    assert event_full_text.search_vector_sv is not None
    assert event_full_text.search_vector_en is not None
    assert event_full_text.search_vector_zh_hans is not None
    assert event_full_text.search_vector_ru is not None
    assert event_full_text.search_vector_ar is not None
    event_2 = EventFactory(id="test:2", data_source=data_source, origin_id=2)
    event_2.keywords.add(keyword)
    event_2.save()
    assert EventSearchIndex.objects.all().count() == 2
    event_2_full_text = EventSearchIndex.objects.get(event=event_2)
    assert event_2_full_text.event == event_2
    assert event_2_full_text.search_vector_fi is not None
    assert event_2_full_text.search_vector_sv is not None
    assert event_2_full_text.search_vector_en is not None
    assert event_2_full_text.search_vector_zh_hans is not None
    assert event_2_full_text.search_vector_ru is not None
    assert event_2_full_text.search_vector_ar is not None


@pytest.mark.skipif(
    not settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED,
    reason="Event search signals disabled",
)
@pytest.mark.django_db
def test_auto_update_event_search_index_on_event_update(
    event, place, keyword, data_source
):
    event.keywords.add(keyword)
    event.save()
    assert EventSearchIndex.objects.all().count() == 1
    event_full_text = EventSearchIndex.objects.first()
    assert event_full_text.event == event
    assert event_full_text.place == place
    assert event_full_text.event_last_modified_time == event.last_modified_time
    assert event_full_text.place_last_modified_time == place.last_modified_time
    assert event_full_text.search_vector_fi is not None
    assert event_full_text.search_vector_sv is not None
    assert event_full_text.search_vector_en is not None
    assert event_full_text.search_vector_zh_hans is not None
    assert event_full_text.search_vector_ru is not None
    assert event_full_text.search_vector_ar is not None
    assert event.name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    event.name_fi = "Päivitetty nimi"
    event.save()
    assert EventSearchIndex.objects.all().count() == 1
    updated_event_full_text = EventSearchIndex.objects.first()
    assert updated_event_full_text.event == event
    assert updated_event_full_text.place == place
    assert updated_event_full_text.search_vector_fi is not None
    assert updated_event_full_text.search_vector_sv is not None
    assert updated_event_full_text.search_vector_en is not None
    assert updated_event_full_text.search_vector_zh_hans is not None
    assert updated_event_full_text.search_vector_ru is not None
    assert updated_event_full_text.search_vector_ar is not None
    assert event.name_fi[:4].lower() in str(updated_event_full_text.search_vector_fi)


@pytest.mark.skipif(
    not settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED,
    reason="Event search signals disabled",
)
@pytest.mark.django_db
def test_auto_update_event_search_index_on_event_delete(event, place, data_source):
    assert EventSearchIndex.objects.all().count() == 1
    EventFactory(id="test:2", data_source=data_source, origin_id=2)
    assert EventSearchIndex.objects.all().count() == 2
    event.delete()
    assert EventSearchIndex.objects.all().count() == 1


@pytest.mark.skipif(
    not settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED,
    reason="Event search signals disabled",
)
@pytest.mark.django_db
def test_auto_update_event_search_index_on_place_update(event, place, data_source):
    assert EventSearchIndex.objects.all().count() == 1
    event_full_text = EventSearchIndex.objects.first()
    assert event_full_text.event == event
    assert event_full_text.place == place
    assert event_full_text.event_last_modified_time == event.last_modified_time
    assert event_full_text.place_last_modified_time == place.last_modified_time
    assert event_full_text.search_vector_fi is not None
    assert event_full_text.search_vector_sv is not None
    assert event_full_text.search_vector_en is not None
    assert event_full_text.search_vector_zh_hans is not None
    assert event_full_text.search_vector_ru is not None
    assert event_full_text.search_vector_ar is not None
    assert place.name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    place.name_fi = "Päivitetty paikka"
    place.save()
    assert EventSearchIndex.objects.all().count() == 1
    updated_event_full_text = EventSearchIndex.objects.first()
    assert updated_event_full_text.event == event
    assert updated_event_full_text.place == place
    assert updated_event_full_text.search_vector_fi is not None
    assert updated_event_full_text.search_vector_sv is not None
    assert updated_event_full_text.search_vector_en is not None
    assert updated_event_full_text.search_vector_zh_hans is not None
    assert updated_event_full_text.search_vector_ru is not None
    assert updated_event_full_text.search_vector_ar is not None
    assert place.name_fi[:4].lower() in str(updated_event_full_text.search_vector_fi)


@pytest.mark.skipif(
    not settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED,
    reason="Event search signals disabled",
)
@pytest.mark.django_db
def test_auto_update_event_search_index_on_place_delete(event, place, data_source):
    assert EventSearchIndex.objects.all().count() == 1
    place_2 = PlaceFactory(id="test_place:2", data_source=data_source, origin_id=2)
    place_2_name_fi = place_2.name_fi
    event_2 = EventFactory(
        id="test:2", data_source=data_source, origin_id=2, location=place_2
    )
    assert EventSearchIndex.objects.all().count() == 2
    event_full_text = EventSearchIndex.objects.filter(event=event_2).first()
    assert event_full_text.event == event_2
    assert event_full_text.place == place_2
    assert event_full_text.search_vector_fi is not None
    assert place_2_name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    event_2.location = None
    event_2.save()
    place_2.delete()
    assert EventSearchIndex.objects.all().count() == 2
    event_full_text = EventSearchIndex.objects.filter(event=event_2).first()
    assert event_full_text.event == event_2
    assert event_full_text.place is None
    assert event_full_text.search_vector_fi is not None
    assert place_2_name_fi[:4].lower() not in str(event_full_text.search_vector_fi)


@pytest.mark.skipif(
    not settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED,
    reason="Event search signals disabled",
)
@pytest.mark.django_db
def test_auto_update_event_search_index_on_keyword_update(
    event, place, keyword, data_source
):
    event.keywords.add(keyword)
    assert EventSearchIndex.objects.all().count() == 1
    event_full_text = EventSearchIndex.objects.first()
    assert event_full_text.event == event
    assert event_full_text.place == place
    assert event_full_text.event_last_modified_time == event.last_modified_time
    assert event_full_text.place_last_modified_time == place.last_modified_time
    assert event_full_text.search_vector_fi is not None
    assert event_full_text.search_vector_sv is not None
    assert event_full_text.search_vector_en is not None
    assert event_full_text.search_vector_zh_hans is not None
    assert event_full_text.search_vector_ru is not None
    assert event_full_text.search_vector_ar is not None
    assert keyword.name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    keyword.name_fi = "Päivitetty avainsana"
    keyword.save()
    assert EventSearchIndex.objects.all().count() == 1
    updated_event_full_text = EventSearchIndex.objects.first()
    assert updated_event_full_text.event == event
    assert updated_event_full_text.place == place
    assert updated_event_full_text.search_vector_fi is not None
    assert updated_event_full_text.search_vector_sv is not None
    assert updated_event_full_text.search_vector_en is not None
    assert updated_event_full_text.search_vector_zh_hans is not None
    assert updated_event_full_text.search_vector_ru is not None
    assert updated_event_full_text.search_vector_ar is not None
    assert keyword.name_fi[:4].lower() in str(updated_event_full_text.search_vector_fi)


@pytest.mark.skipif(
    not settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED,
    reason="Event search signals disabled",
)
@pytest.mark.django_db
def test_auto_update_event_search_index_on_keyword_delete(
    event, place, keyword, data_source
):
    event.keywords.add(keyword)
    assert EventSearchIndex.objects.all().count() == 1
    event_full_text = EventSearchIndex.objects.first()
    assert event_full_text.event == event
    assert event_full_text.place == place
    assert event_full_text.event_last_modified_time == event.last_modified_time
    assert event_full_text.place_last_modified_time == place.last_modified_time
    assert event_full_text.search_vector_fi is not None
    assert event_full_text.search_vector_sv is not None
    assert event_full_text.search_vector_en is not None
    assert event_full_text.search_vector_zh_hans is not None
    assert event_full_text.search_vector_ru is not None
    assert event_full_text.search_vector_ar is not None
    assert keyword.name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    event.keywords.remove(keyword)
    assert EventSearchIndex.objects.all().count() == 1
    updated_event_full_text = EventSearchIndex.objects.first()
    assert updated_event_full_text.event == event
    assert updated_event_full_text.place == place
    assert updated_event_full_text.search_vector_fi is not None
    assert updated_event_full_text.search_vector_sv is not None
    assert updated_event_full_text.search_vector_en is not None
    assert updated_event_full_text.search_vector_zh_hans is not None
    assert updated_event_full_text.search_vector_ru is not None
    assert updated_event_full_text.search_vector_ar is not None
    assert keyword.name_fi[:4].lower() not in str(
        updated_event_full_text.search_vector_fi
    )


@pytest.mark.skipif(
    not settings.EVENT_SEARCH_INDEX_SIGNALS_ENABLED,
    reason="Event search signals disabled",
)
@pytest.mark.django_db
def test_auto_update_event_search_index_on_keywords_clear(
    event, place, keyword, data_source
):
    event.keywords.add(keyword)
    assert EventSearchIndex.objects.all().count() == 1
    event_full_text = EventSearchIndex.objects.first()
    assert event_full_text.event == event
    assert event_full_text.place == place
    assert event_full_text.event_last_modified_time == event.last_modified_time
    assert event_full_text.place_last_modified_time == place.last_modified_time
    assert event_full_text.search_vector_fi is not None
    assert event_full_text.search_vector_sv is not None
    assert event_full_text.search_vector_en is not None
    assert event_full_text.search_vector_zh_hans is not None
    assert event_full_text.search_vector_ru is not None
    assert event_full_text.search_vector_ar is not None
    assert keyword.name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    event.keywords.clear()
    assert EventSearchIndex.objects.all().count() == 1
    updated_event_full_text = EventSearchIndex.objects.first()
    assert updated_event_full_text.event == event
    assert updated_event_full_text.place == place
    assert updated_event_full_text.search_vector_fi is not None
    assert updated_event_full_text.search_vector_sv is not None
    assert updated_event_full_text.search_vector_en is not None
    assert updated_event_full_text.search_vector_zh_hans is not None
    assert updated_event_full_text.search_vector_ru is not None
    assert updated_event_full_text.search_vector_ar is not None
    assert keyword.name_fi[:4].lower() not in str(
        updated_event_full_text.search_vector_fi
    )


@pytest.mark.django_db
def test_index_rebuild_time_limit():
    now = timezone.now()
    EventFactory(end_time=now + relativedelta(months=1))
    EventFactory(end_time=now + relativedelta(months=10))
    EventFactory(end_time=now + relativedelta(months=100))
    EventFactory(end_time=now - relativedelta(months=1))
    EventFactory(end_time=now - relativedelta(months=10))
    EventFactory(end_time=now - relativedelta(months=100))
    EventFactory(end_time=now - relativedelta(months=35))
    EventFactory(end_time=now - relativedelta(months=36))
    EventFactory(end_time=now - relativedelta(months=37))
    EventFactory(end_time=None)
    call_command("rebuild_event_search_index")
    assert EventSearchIndex.objects.all().count() == 7
