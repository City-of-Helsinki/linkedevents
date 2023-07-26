import os
from datetime import time, timedelta
from unittest.mock import patch

import pytest
from django.test import TestCase
from django.utils import timezone

from events.importer.kulke import KulkeImporter, parse_age_range, parse_course_time
from events.models import Event, EventAggregate, EventAggregateMember
from events.tests.factories import EventFactory, KeywordFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("Pölyt pois taidehistoriasta! Rooman ylväät pylväät", (None, None)),
        ("(3 kk–4 v) klo 9.30–10.15 kevään mittainen lyhytkurssi", (None, None)),
        ("4-6 vuotiaille (yhdessä aikuisen kanssa) ma klo 10-11.30", (4, 6)),
        ("Työpaja ja esitys 9-12-vuotiaille", (9, 12)),
        ("(3–5 v) klo 13-15", (3, 5)),
        ("5–6 v klo 15.45–17.15", (5, 6)),
        ("13–18 v klo 14.00–15.30", (13, 18)),
        ("8–12 år kl 15.30–17.00", (8, 12)),
        ("11–18 år kl 17.15–19.30", (11, 18)),
    ],
)
def test_parse_age_range_returns_correct_result(test_input, expected):
    assert parse_age_range(test_input) == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("Pölyt pois taidehistoriasta! Rooman ylväät pylväät", (None, None)),
        ("Työpaja ja esitys 9-12-vuotiaille", (None, None)),
        ("(3–5 v) klo 13-15", (time(hour=13), time(hour=15))),
        ("7–9 v klo 10.30–12", (time(hour=10, minute=30), time(hour=12))),
        (
            "(3–5 v) klo 10.30–12.30",
            (time(hour=10, minute=30), time(hour=12, minute=30)),
        ),
        (
            "11-13 v klo 16-17.30 lukuvuoden mittainen kurssi",
            (time(hour=16), time(hour=17, minute=30)),
        ),
        ("8–12 v klo 15.30–17.00", (time(hour=15, minute=30), time(hour=17))),
        (
            "11–18 år kl 17.15–19.30",
            (time(hour=17, minute=15), time(hour=19, minute=30)),
        ),
        ("8–12 år kl 15.30–17.00", (time(hour=15, minute=30), time(hour=17))),
        (
            "4-6 vuotiaille (yhdessä aikuisen kanssa) ma klo 10-11.30",
            (time(hour=10), time(hour=11, minute=30)),
        ),
    ],
)
def test_parse_course_time_returns_correct_result(test_input, expected):
    assert parse_course_time(test_input) == expected


class TestKulkeImporter(TestCase):
    def setUp(self) -> None:
        with patch.object(KulkeImporter, "fetch_kulke_categories", return_value={}):
            self.importer = KulkeImporter(options={})
        self.data_source = self.importer.data_source

    def _create_super_event(self, events: list[Event]) -> Event:
        aggregate = EventAggregate.objects.create()
        super_event = EventFactory(
            super_event_type=Event.SuperEventType.RECURRING,
            data_source=self.data_source,
            id="linkedevents:agg-{}".format(aggregate.id),
        )
        super_event.save()
        aggregate.super_event = super_event
        aggregate.save()
        event_aggregates = [
            EventAggregateMember(event=event, event_aggregate=aggregate)
            for event in events
        ]
        EventAggregateMember.objects.bulk_create(event_aggregates)
        return super_event

    def assert_event_soft_deleted(self, event_id: str, deleted: bool):
        """
        Assert that the event with the given ID has the given deleted status,
        i.e. it has been soft-deleted if `deleted` is True, and it has not been
        soft-deleted if `deleted` is False.

        If the event does not exist (e.g. due to being actually deleted), the
        test fails.
        """
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            self.fail(f"Event with ID {event_id} does not exist")
        self.assertEqual(event.deleted, deleted)

    @pytest.mark.django_db
    def test_html_format(self):
        text = (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit.{0}"
            "{0}"
            "Nam quam urna.{0}"
            "Etiam maximus ex tellus, elementum fermentum tellus bibendum id.{0}"
            "Praesent sodales purus libero.{0}"
            "{0}"
            "Vestibulum lacinia interdum nisi eu vehicula."
        ).format(os.linesep)

        html_text = KulkeImporter._html_format(text)
        expected_text = (
            "<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>"
            "<p>Nam quam urna.<br>"
            "Etiam maximus ex tellus, elementum fermentum tellus bibendum id.<br>"
            "Praesent sodales purus libero.</p>"
            "<p>Vestibulum lacinia interdum nisi eu vehicula.</p>"
        )
        self.assertEqual(html_text, expected_text)

    @pytest.mark.django_db
    def test__update_super_event(self):
        now = timezone.now()
        kw1, kw2, kw3 = KeywordFactory.create_batch(3, data_source=self.data_source)
        event_1 = EventFactory(
            name="Toistuva tapahtuma 1",
            name_en="Recurring Event 1",
            description="Long description",
            short_description="Short description",
            start_time=now - timedelta(hours=24),
            end_time=now - timedelta(hours=23),
            data_source=self.data_source,
        )
        event_1.keywords.add(kw1, kw2)
        event_1.save()
        event_2 = EventFactory(
            name="Toistuva tapahtuma 2",
            name_en="Recurring Event 2",
            description=event_1.description,
            short_description="A different short description",
            start_time=now,
            end_time=now + timedelta(hours=1),
            data_source=self.data_source,
        )
        event_2.keywords.add(kw2, kw3)
        event_2.save()
        super_event = self._create_super_event([event_1, event_2])

        self.importer._update_super_event(super_event, [event_1, event_2])
        # The super event should have the common part for the name
        self.assertEqual(super_event.name, "Toistuva tapahtuma")
        self.assertEqual(super_event.name_en, "Recurring Event")
        # The start/end time should be the start/end time of the first/last event
        self.assertEqual(super_event.start_time, event_1.start_time)
        self.assertEqual(super_event.end_time, event_2.end_time)
        # The super event should have the common subset of keywords
        self.assertEqual(
            set(super_event.keywords.all().values_list("id", flat=True)), {str(kw2.id)}
        )
        # A field that's the same for all member events should be populated in the super event
        self.assertEqual(super_event.description, event_1.description)
        # No common value => field should be empty in the super event
        self.assertIsNone(super_event.short_description)

    @pytest.mark.django_db
    def test__update_super_event_default_name(self):
        now = timezone.now()
        event_1 = EventFactory(
            name="Joku tapahtuma",
            name_en="Some Event",
            start_time=now - timedelta(hours=24),
            end_time=now - timedelta(hours=23),
            data_source=self.data_source,
        )
        event_2 = EventFactory(
            name="Ei yhteistä osaa nimessä",
            name_en="No common part in the name",
            start_time=now,
            end_time=now + timedelta(hours=1),
            data_source=self.data_source,
        )
        super_event = self._create_super_event([event_1, event_2])

        self.importer._update_super_event(super_event, [event_1, event_2])
        # If the name does not have a common part, default to the first event's name
        self.assertEqual(super_event.name, "Joku tapahtuma")
        self.assertEqual(super_event.name_en, "Some Event")

    @pytest.mark.django_db
    def test__save_super_event(self):
        event_1 = EventFactory(id="kulke:1", data_source=self.data_source, origin_id=1)
        event_2 = EventFactory(id="kulke:2", data_source=self.data_source, origin_id=2)
        event_3 = EventFactory(id="kulke:3", data_source=self.data_source, origin_id=3)

        # Create a super event with all three events
        self.importer._save_super_event(
            {event_1.origin_id, event_2.origin_id, event_3.origin_id}
        )

        event_1.refresh_from_db()
        super_event = event_1.super_event
        self.assertEqual(
            set(member.event_id for member in super_event.aggregate.members.all()),
            {event_1.id, event_2.id, event_3.id},
        )

        # Simulate a situation where one of the events is no longer associated with the super event in Elis
        self.importer._save_super_event({event_1.origin_id, event_2.origin_id})

        event_1.refresh_from_db()
        super_event = event_1.super_event
        self.assertEqual(
            set(member.event_id for member in super_event.aggregate.members.all()),
            {event_1.id, event_2.id},
        )
        self.assertTrue(Event.objects.filter(id=event_3.id).exists())

        # If there is only one event left in the super event, the super event should be deleted
        # Deleting the event itself is not the responsibility of `_save_super_event`
        self.importer._save_super_event({event_1.origin_id})
        event_1.refresh_from_db()
        self.assertIsNone(event_1.super_event)
        self.assertTrue(Event.objects.filter(id=event_2.id).exists())
        self.assertTrue(Event.objects.filter(id=event_3.id).exists())

    @pytest.mark.django_db
    def test__handle_removed_events(self):
        """Test that removing"""
        now = timezone.now()
        # Event that exists in the DB but not in  Elis -- will be removed
        event_1 = EventFactory(
            data_source=self.data_source, origin_id=1, start_time=now
        )
        # Event that exists in Elis -- won't be removed
        event_2 = EventFactory(
            data_source=self.data_source, origin_id=2, start_time=now
        )
        # Old event, outside the date range of the Elis search -- won't be removed
        event_3 = EventFactory(
            data_source=self.data_source,
            origin_id=3,
            start_time=now - timedelta(days=90),
        )

        self.importer._handle_removed_events(
            elis_event_ids=[event_2.origin_id],
            begin_date=now - timedelta(days=60),
        )

        self.assert_event_soft_deleted(event_1.id, True)
        self.assert_event_soft_deleted(event_2.id, False)
        self.assert_event_soft_deleted(event_3.id, False)

    @pytest.mark.django_db
    def test__handle_removed_events_superevent(self):
        now = timezone.now()
        # This super event is not in Elis. The super event with all its member events should be removed.
        super_1_event_1 = EventFactory(
            data_source=self.data_source, origin_id=1, start_time=now
        )
        super_1_event_2 = EventFactory(
            data_source=self.data_source, origin_id=2, start_time=now
        )
        super_1 = self._create_super_event([super_1_event_1, super_1_event_2])

        # This super event is in Elis. It should not be removed.
        super_2_event_1 = EventFactory(
            data_source=self.data_source, origin_id=3, start_time=now
        )
        super_2_event_2 = EventFactory(
            data_source=self.data_source, origin_id=4, start_time=now
        )
        super_2 = self._create_super_event([super_2_event_1, super_2_event_2])

        # This super event is empty to begin with -- it should be removed
        super_3 = self._create_super_event([])

        self.importer._handle_removed_events(
            elis_event_ids=[super_2_event_1.origin_id, super_2_event_2.origin_id],
            begin_date=now - timedelta(days=60),
        )

        self.assert_event_soft_deleted(super_1_event_1.id, True)
        self.assert_event_soft_deleted(super_1_event_2.id, True)
        self.assert_event_soft_deleted(super_1.id, True)
        self.assert_event_soft_deleted(super_2_event_1.id, False)
        self.assert_event_soft_deleted(super_2_event_2.id, False)
        self.assert_event_soft_deleted(super_2.id, False)
        self.assert_event_soft_deleted(super_3.id, True)
