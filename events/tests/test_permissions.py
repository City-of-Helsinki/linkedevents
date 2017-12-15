from unittest.mock import MagicMock

from django.test import TestCase
from django_orghierarchy.models import Organization

from ..models import DataSource, Event, PublicationStatus
from ..permissions import UserModelPermissionMixin


class TestUserModelPermissionMixin(TestCase):

    def setUp(self):
        self.instance = UserModelPermissionMixin()

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

    def test_is_admin(self):
        self.assertRaises(
            NotImplementedError,
            self.instance.is_admin,
            self.org,
        )

    def test_is_regular_user(self):
        self.assertRaises(
            NotImplementedError,
            self.instance.is_regular_user,
            self.org,
        )

    def test_can_edit_event(self):
        # test for admin user
        self.instance.is_admin = MagicMock(return_value=True)

        can_edit = self.instance.can_edit_event(self.org, PublicationStatus.PUBLIC)
        self.assertTrue(can_edit)
        can_edit = self.instance.can_edit_event(self.org, PublicationStatus.DRAFT)
        self.assertTrue(can_edit)

        # test for regular user
        self.instance.is_admin = MagicMock(return_value=False)
        self.instance.is_regular_user = MagicMock(return_value=True)

        can_edit = self.instance.can_edit_event(self.org, PublicationStatus.PUBLIC)
        self.assertFalse(can_edit)
        can_edit = self.instance.can_edit_event(self.org, PublicationStatus.DRAFT)
        self.assertTrue(can_edit)

        # test for other users
        self.instance.is_admin = MagicMock(return_value=False)
        self.instance.is_regular_user = MagicMock(return_value=False)

        can_edit = self.instance.can_edit_event(self.org, PublicationStatus.PUBLIC)
        self.assertFalse(can_edit)
        can_edit = self.instance.can_edit_event(self.org, PublicationStatus.DRAFT)
        self.assertFalse(can_edit)

    def test_get_editable_events(self):
        event_1 = Event.objects.create(
            id='event-1',
            name='event-1',
            data_source=self.data_source,
            publisher=self.org,
            publication_status=PublicationStatus.PUBLIC,
        )
        event_2 = Event.objects.create(
            id='event-2',
            name='event-2',
            data_source=self.data_source,
            publisher=self.org,
            publication_status=PublicationStatus.DRAFT,
        )

        total_qs = Event.objects.all()
        # test for admin user
        self.instance.is_admin = MagicMock(return_value=True)
        qs = self.instance.get_editable_events(self.org, total_qs)
        self.assertQuerysetEqual(qs, [repr(event_1), repr(event_2)], ordered=False)

        # test for regular user
        self.instance.is_admin = MagicMock(return_value=False)
        self.instance.is_regular_user = MagicMock(return_value=True)
        qs = self.instance.get_editable_events(self.org, total_qs)
        self.assertQuerysetEqual(qs, [repr(event_2)])

        # test for other users
        self.instance.is_admin = MagicMock(return_value=False)
        self.instance.is_regular_user = MagicMock(return_value=False)
        qs = self.instance.get_editable_events(self.org, total_qs)
        self.assertQuerysetEqual(qs, [])
