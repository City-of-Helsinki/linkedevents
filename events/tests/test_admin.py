from django.contrib import admin
from django.test import TestCase

from events.models import Event, PublicationStatus
from events.tests.factories import EventFactory, KeywordFactory
from helevents.tests.factories import UserFactory


class TestEventAdmin(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = UserFactory(username="testadmin", is_staff=True, is_superuser=True)

        cls.event = EventFactory(data_source__pk="system")
        cls.event_change_url = f"/admin/events/event/{cls.event.id}/change/"
        cls.event_add_url = "/admin/events/event/add/"

        cls.keyword = KeywordFactory(
            publisher=cls.event.publisher, data_source=cls.event.data_source
        )

    def _get_request_data(self, update_data=None):
        data = {
            "name_fi": "Test event",
            "publisher": self.event.publisher_id,
            "start_time_0": "2024-06-12",
            "start_time_1": "06:00:00",
            "end_time_0": "2024-06-12",
            "end_time_1": "14:00:00",
            "keywords": [self.keyword.id],
            "provider_fi": "Test provider",
            "event_status": Event.Status.SCHEDULED,
            "publication_status": PublicationStatus.PUBLIC,
            "maximum_attendee_capacity": 1000000,
            "minimum_attendee_capacity": 500000,
        }

        if update_data:
            data.update(update_data)

        return data

    def setUp(self):
        self.client.force_login(self.admin)

    def test_event_admin_is_registered(self):
        is_registered = admin.site.is_registered(Event)
        self.assertTrue(is_registered)

    def test_create_event_with_large_max_and_min_attendee_capacity(self):
        self.assertEqual(Event.objects.count(), 1)

        self.client.post(self.event_add_url, self._get_request_data())

        self.assertEqual(Event.objects.count(), 2)

        new_event = Event.objects.last()
        self.assertEqual(new_event.maximum_attendee_capacity, 1000000)
        self.assertEqual(new_event.minimum_attendee_capacity, 500000)

    def test_update_event_with_large_max_and_min_attendee_capacity(self):
        self.assertEqual(Event.objects.count(), 1)
        self.assertIsNone(self.event.minimum_attendee_capacity)
        self.assertIsNone(self.event.maximum_attendee_capacity)

        self.client.post(self.event_change_url, self._get_request_data())

        self.assertEqual(Event.objects.count(), 1)

        self.event.refresh_from_db()
        self.assertEqual(self.event.maximum_attendee_capacity, 1000000)
        self.assertEqual(self.event.minimum_attendee_capacity, 500000)
