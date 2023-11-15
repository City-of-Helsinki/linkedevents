from io import StringIO

import pytest
from django.core.management import call_command

from events.models import EventFullText
from events.tests.factories import EventFactory

create_no_refresh = "\n".join(
    [
        "Creating events_eventfulltext materialized view (this may take some seconds)",
        "Done!",
        "Checking if refresh is needed...",
        "Refresh not needed!",
        "",
    ]
)

create_refresh = "\n".join(
    [
        "Creating events_eventfulltext materialized view (this may take some seconds)",
        "Done!",
        "Checking if refresh is needed...",
        "Refreshing events_eventfulltext materialized view (this may take some seconds)",
        "Done!",
        "",
    ]
)


@pytest.mark.django_db(transaction=True)
def test_refresh_no_changes(event, place):
    out = StringIO()
    call_command("refresh_full_text", "--create", stdout=out)
    call_command("refresh_full_text", stdout=out)

    assert out.getvalue() == create_no_refresh
    assert EventFullText.objects.all().count() == 1


@pytest.mark.django_db()
def test_create_with_valid_overrides(settings):
    settings.FULL_TEXT_WEIGHT_OVERRIDES = {
        "event.name": "D",
        "event.short_description": "D",
        "event.description": "A",
        "place.name": "D",
        "event_keywords.name": "D",
    }
    out = StringIO()
    call_command("refresh_full_text", "--create-no-transaction", stdout=out)

    assert "Applied weight override for field event.name to D" in out.getvalue()
    assert (
        "Applied weight override for field event.short_description to D"
        in out.getvalue()
    )
    assert "Applied weight override for field event.description to A" in out.getvalue()
    assert "Applied weight override for field place.name to D" in out.getvalue()
    assert (
        "Applied weight override for field event_keywords.name to D" in out.getvalue()
    )
    assert "Failed to apply weight override" not in out.getvalue()


@pytest.mark.django_db()
def test_create_with_invalid_override(settings):
    settings.FULL_TEXT_WEIGHT_OVERRIDES = {
        "event.foobar": "D",
    }
    out = StringIO()
    call_command("refresh_full_text", "--create-no-transaction", stdout=out)

    assert "Failed to apply weight override for event.foobar" in out.getvalue()
    assert "Applied weight override for" not in out.getvalue()


@pytest.mark.django_db()
def test_refresh_event_modified(event, place):
    out = StringIO()
    call_command("refresh_full_text", "--create-no-transaction", stdout=out)
    event.name_fi = "Oho"
    event.save()
    call_command("refresh_full_text", stdout=out)

    assert out.getvalue() == create_refresh
    assert EventFullText.objects.all().count() == 1


@pytest.mark.django_db()
def test_refresh_event_inserted(event, place):
    out = StringIO()
    call_command("refresh_full_text", "--create-no-transaction", stdout=out)
    EventFactory()
    call_command("refresh_full_text", stdout=out)

    assert out.getvalue() == create_refresh
    assert EventFullText.objects.all().count() == 2


@pytest.mark.django_db()
def test_refresh_event_deleted(event, place):
    out = StringIO()
    call_command("refresh_full_text", "--create-no-transaction", stdout=out)
    event.delete()
    call_command("refresh_full_text", stdout=out)

    assert out.getvalue() == create_refresh
    assert EventFullText.objects.all().count() == 0


@pytest.mark.django_db()
def test_refresh_event_added_and_deleted(event, place):
    out = StringIO()
    call_command("refresh_full_text", "--create-no-transaction", stdout=out)
    EventFactory()
    event.delete()
    call_command("refresh_full_text", stdout=out)

    assert out.getvalue() == create_refresh
    assert EventFullText.objects.all().count() == 1


@pytest.mark.django_db()
def test_refresh_place_modified(event, place):
    out = StringIO()
    call_command("refresh_full_text", "--create-no-transaction", stdout=out)
    place.name_fi = "Some other place"
    place.save()
    call_command("refresh_full_text", stdout=out)

    assert out.getvalue() == create_refresh
    assert EventFullText.objects.all().count() == 1


# Not testing:
# 1) Place deletion: Protected by event.location relation
# 2) Place addition: Not relevant
