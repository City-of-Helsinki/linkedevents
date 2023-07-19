from django.contrib.auth import get_user_model
from django.test import TestCase
from django_orghierarchy.models import Organization

from helevents.tests.factories import UserFactory

from ..models import DataSource, Event, Image, KeywordSet, PublicationStatus


class TestImage(TestCase):
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
        self.image = Image.objects.create(
            name="image",
            data_source=self.data_source,
            publisher=self.org,
            url="http://fake.url/image/",
        )

    def test_can_be_edited_by_super_user(self):
        self.user.is_superuser = True
        self.user.save()

        can_be_edited = self.image.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_cannot_be_edited_by_random_user(self):
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

    def test_can_be_deleted_by_super_user(self):
        self.user.is_superuser = True
        self.user.save()

        can_be_deleted = self.image.can_be_deleted_by(self.user)
        self.assertTrue(can_be_deleted)

    def test_cannot_be_deleted_by_random_user(self):
        can_be_deleted = self.image.can_be_deleted_by(self.user)
        self.assertFalse(can_be_deleted)

    def test_cannot_be_deleted_by_regular_user(self):
        self.org.regular_users.add(self.user)

        can_be_deleted = self.image.can_be_deleted_by(self.user)
        self.assertFalse(can_be_deleted)

    def test_can_be_deleted_by_admin_user(self):
        self.org.admin_users.add(self.user)

        can_be_deleted = self.image.can_be_deleted_by(self.user)
        self.assertTrue(can_be_deleted)


class TestImageExternal(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user2 = UserFactory()

        self.data_source = DataSource.objects.create(
            id="ds",
            name="data-source",
            api_key="test_api_key",
            user_editable_resources=True,
        )
        self.image = Image.objects.create(
            name="image",
            data_source=self.data_source,
            publisher=None,
            created_by=self.user,
            url="http://fake.url/image/",
        )

    def test_can_be_edited_by_external_user(self):
        can_be_edited = self.image.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_cannot_be_edited_by_other_external_users(self):
        can_be_edited = self.image.can_be_edited_by(self.user2)
        self.assertFalse(can_be_edited)


class TestEvent(TestCase):
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
        self.event_1 = Event.objects.create(
            id="ds:event-1",
            name="event-1",
            data_source=self.data_source,
            publisher=self.org,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_2 = Event.objects.create(
            id="ds:event-2",
            name="event-2",
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


class TestKeywordSet(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create(username="testuser")

        self.data_source = DataSource.objects.create(
            name="data-source",
            user_editable_resources=True,
        )
        self.org = Organization.objects.create(
            name="org",
            origin_id="123",
            data_source=self.data_source,
        )
        self.keywordSet = KeywordSet.objects.create(
            name="keyword-set",
            data_source=self.data_source,
            organization=self.org,
        )

    def test_can_be_edited_by_super_user(self):
        self.user.is_superuser = True
        self.user.save()

        can_be_edited = self.keywordSet.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_cannot_be_edited_by_random_user(self):
        can_be_edited = self.keywordSet.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_cannot_be_edited_by_regular_user(self):
        self.org.regular_users.add(self.user)

        can_be_edited = self.keywordSet.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_can_be_edited_by_admin_user(self):
        self.org.admin_users.add(self.user)

        can_be_edited = self.keywordSet.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)
