from django.contrib.auth import get_user_model
from django.test import TestCase
from django_orghierarchy.models import Organization

from events.models import DataSource, Event
from registrations.models import Registration


class TestRegistration(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create(username="testuser")

        self.data_source = DataSource.objects.create(
            id="ds",
            name="data-source",
            api_key="test_api_key",
            user_editable_resources=True,
        )
        self.org = Organization.objects.create(
            name="org",
            origin_id="org",
            data_source=self.data_source,
        )
        self.event = Event.objects.create(
            id="ds:event",
            name="event",
            data_source=self.data_source,
            publisher=self.org,
        )
        self.registration = Registration.objects.create(
            event=self.event,
        )

    def test_can_be_edited_by_super_user(self):
        self.user.is_superuser = True
        self.user.save()

        can_be_edited = self.registration.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_cannot_be_edited_by_random_user(self):
        can_be_edited = self.registration.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_cannot_be_edited_by_regular_user(self):
        self.org.regular_users.add(self.user)

        can_be_edited = self.registration.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_can_be_edited_by_admin_user(self):
        self.org.admin_users.add(self.user)

        can_be_edited = self.registration.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)
