from django.contrib.auth import get_user_model
from django.test import TestCase
from django_orghierarchy.models import Organization

from ..models import DataSource, Event, Image, PublicationStatus


class TestImage(TestCase):

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create(username='testuser')

        self.data_source = DataSource.objects.create(
            id='ds',
            name='data-source',
            api_key="test_api_key",
            user_editable=True,
        )
        self.org = Organization.objects.create(
            name='org',
            origin_id='org',
            data_source=self.data_source,
        )
        self.image = Image.objects.create(
            name='image',
            data_source=self.data_source,
            publisher=self.org,
            url='http://fake.url/image/',
        )

    def test_can_be_edited_by_super_user(self):
        self.user.is_superuser = True
        self.user.save()

        can_be_edited = self.image.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_can_be_edited_by_random_user(self):
        can_be_edited = self.image.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_can_be_edited_by_regular_user(self):
        self.org.regular_users.add(self.user)

        can_be_edited = self.image.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_can_be_edited_by_admin_user(self):
        self.org.admin_users.add(self.user)

        can_be_edited = self.image.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)


class TestEvent(TestCase):

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create(username='testuser')

        self.data_source = DataSource.objects.create(
            id='ds',
            name='data-source',
            api_key="test_api_key",
            user_editable=True,
        )
        self.org = Organization.objects.create(
            name='org',
            origin_id='org',
            data_source=self.data_source,
        )
        self.event_1 = Event.objects.create(
            id='ds:event-1',
            name='event-1',
            data_source=self.data_source,
            publisher=self.org,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_2 = Event.objects.create(
            id='ds:event-2',
            name='event-2',
            data_source=self.data_source,
            publisher=self.org,
            publication_status=PublicationStatus.PUBLIC,
        )

    def test_can_be_edited_by_super_user(self):
        self.user.is_superuser = True
        self.user.save()

        can_be_edited = self.event_1.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

        can_be_edited = self.event_2.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_can_be_edited_by_random_user(self):
        can_be_edited = self.event_1.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

        can_be_edited = self.event_2.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_can_be_edited_by_regular_user(self):
        self.org.regular_users.add(self.user)

        can_be_edited = self.event_1.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)  # can edit draft event

        can_be_edited = self.event_2.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)  # cannot edit public event

    def test_can_be_edited_by_admin_user(self):
        self.org.admin_users.add(self.user)

        can_be_edited = self.event_1.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

        can_be_edited = self.event_2.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)
