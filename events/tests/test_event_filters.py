import pytest

from events.api import EventFilter
from events.models import Event
from events.tests.factories import EventFactory
from events.tests.utils import create_super_event


@pytest.mark.no_use_audit_log
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


@pytest.mark.no_use_audit_log
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
