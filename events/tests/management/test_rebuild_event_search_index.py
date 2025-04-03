import pytest
from django.core.management import call_command

from events.models import EventSearchIndex
from events.tests.factories import EventFactory


@pytest.mark.django_db(transaction=True)
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
    assert place.name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    assert place.name_sv[:4].lower() in str(event_full_text.search_vector_sv)
    assert place.name_en[:4].lower() in str(event_full_text.search_vector_en)
    assert event.name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    assert event.name_sv[:4].lower() in str(event_full_text.search_vector_sv)
    assert event.name_en[:4].lower() in str(event_full_text.search_vector_en)
    assert keyword.name_fi[:4].lower() in str(event_full_text.search_vector_fi)
    assert keyword.name_sv[:4].lower() in str(event_full_text.search_vector_sv)
    assert keyword.name_en[:4].lower() in str(event_full_text.search_vector_en)


@pytest.mark.django_db(transaction=True)
def test_rebuild_search_vectors_with_clean(event, place, data_source):
    second_event = EventFactory(id="test:2", data_source=data_source, origin_id=2)
    call_command("rebuild_event_search_index")
    assert EventSearchIndex.objects.all().count() == 2
    second_event.delete()
    call_command("rebuild_event_search_index", clean=True)
    assert EventSearchIndex.objects.all().count() == 1
