from django.test import TestCase

from events.tests.test_event_get import EventsListTestCaseMixin
from events.tests.utils import versioned_reverse as reverse
from registrations.tests.factories import RegistrationFactory


class FilterEventsByRegistrationCapacitiesV1TestCase(TestCase, EventsListTestCaseMixin):
    @classmethod
    def setUpTestData(cls):
        cls.list_url = reverse("event-list", version="v1")

    def test_get_event_list_registration_remaining_attendee_capacity_gte(self):
        registration = RegistrationFactory(remaining_attendee_capacity=10)
        registration2 = RegistrationFactory(remaining_attendee_capacity=5)
        registration3 = RegistrationFactory(remaining_attendee_capacity=1)

        for capacity, events in [
            (1, [registration.event, registration2.event, registration3.event]),
            (5, [registration.event, registration2.event]),
            (10, [registration.event]),
            (11, []),
        ]:
            with self.subTest():
                self._get_list_and_assert_events(
                    f"registration__remaining_attendee_capacity__gte={capacity}", events
                )

    def test_get_event_list_registration_remaining_waiting_list_capacity_gte(self):
        registration = RegistrationFactory(remaining_waiting_list_capacity=10)
        registration2 = RegistrationFactory(remaining_waiting_list_capacity=5)
        registration3 = RegistrationFactory(remaining_waiting_list_capacity=1)

        for capacity, events in [
            (1, [registration.event, registration2.event, registration3.event]),
            (5, [registration.event, registration2.event]),
            (10, [registration.event]),
            (11, []),
        ]:
            with self.subTest():
                self._get_list_and_assert_events(
                    f"registration__remaining_waiting_list_capacity__gte={capacity}",
                    events,
                )

    def test_get_event_list_registration_remaining_attendee_capacity_isnull(self):
        registration = RegistrationFactory(remaining_attendee_capacity=10)
        registration2 = RegistrationFactory(remaining_attendee_capacity=None)
        registration3 = RegistrationFactory(remaining_attendee_capacity=1)

        for capacity, events in [
            (1, [registration2.event]),
            (0, [registration.event, registration3.event]),
            (True, [registration2.event]),
            (False, [registration.event, registration3.event]),
        ]:
            with self.subTest():
                self._get_list_and_assert_events(
                    f"registration__remaining_attendee_capacity__isnull={capacity}",
                    events,
                )

    def test_get_event_list_registration_remaining_waiting_list_capacity_isnull(self):
        registration = RegistrationFactory(remaining_waiting_list_capacity=10)
        registration2 = RegistrationFactory(remaining_waiting_list_capacity=None)
        registration3 = RegistrationFactory(remaining_waiting_list_capacity=1)

        for capacity, events in [
            (1, [registration2.event]),
            (0, [registration.event, registration3.event]),
            (True, [registration2.event]),
            (False, [registration.event, registration3.event]),
        ]:
            with self.subTest():
                self._get_list_and_assert_events(
                    f"registration__remaining_waiting_list_capacity__isnull={capacity}",
                    events,
                )
