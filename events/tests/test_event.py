import operator
from collections.abc import Callable

import pytest


@pytest.mark.django_db
def test_deleted_event_can_have_deprecated_keyword(event, keyword):
    keyword.deprecated = True
    keyword.save()
    event.deleted = True
    event.save()
    event.keywords.set([keyword])
    event.save()
    event.keywords.set([])
    event.audience.set([keyword])
    event.save()


@pytest.mark.django_db
def test_event_cannot_replace_itself(event):
    event.replaced_by = event
    event.deprecated = True
    with pytest.raises(Exception):  # noqa: B017
        event.save()


@pytest.mark.django_db
def test_prevent_circular_event_replacement(event, event2, event3):
    event.replaced_by = event2
    event.save()
    event2.replaced_by = event3
    event2.save()
    event3.replaced_by = event
    with pytest.raises(Exception):  # noqa: B017
        event.save()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "skip_last_modified_time,compare_time,compare_user",
    [[False, operator.gt, operator.is_], [True, operator.eq, operator.is_not]],
)
def test_event_update_fields_updates_last_modified_time(
    event, skip_last_modified_time, compare_time: Callable, compare_user: Callable
):
    old_last_modified_time = event.last_modified_time
    event.name = "New name"
    event.save(update_fields=["name"], skip_last_modified_time=skip_last_modified_time)
    event.refresh_from_db()

    assert compare_time(event.last_modified_time, old_last_modified_time)
    assert compare_user(event.last_modified_by_id, None)
