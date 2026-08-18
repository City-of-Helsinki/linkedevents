from datetime import date

import pytest

from events.renderers.docx import DateRange

from .utils import versioned_reverse as reverse


@pytest.mark.django_db
def test_docx_renderer(api_client, event, place):
    event.description_en = "Test event English description"
    event.name_en = "Test event English name"
    event.headline = "Test event headline"
    event.save()

    response = api_client.get(
        f"{reverse('event-list')}?format=docx&location={place.id.replace(' ', '%20')}"
    )
    assert response.status_code == 200


def test_date_range_supports_all_ordering_comparisons():
    earlier = DateRange(date(2026, 1, 1), date(2026, 1, 2))
    later = DateRange(date(2026, 2, 1), date(2026, 2, 2))
    equal = DateRange(date(2026, 1, 1), date(2026, 1, 2))
    same_start_shorter = DateRange(date(2026, 1, 1), date(2026, 1, 2))
    same_start_longer = DateRange(date(2026, 1, 1), date(2026, 1, 3))

    assert earlier < later
    assert earlier <= later
    assert later > earlier
    assert later >= earlier
    assert earlier != later
    assert earlier == equal
    assert same_start_shorter < same_start_longer
