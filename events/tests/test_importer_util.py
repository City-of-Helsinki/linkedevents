import pytest

from events.importer.util import replace_location
from events.models import Event


@pytest.mark.django_db
def test_replace_location_by_different_source(place, place2, other_data_source, event):
    assert event.location == place
    place2.name = place.name
    place2.save()
    replace_location(replace=place, by_source=other_data_source.id)
    updated_event = Event.objects.get(id=event.id)
    assert updated_event.location == place2
