from datetime import timedelta

import freezegun
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone, translation
from django.utils.timezone import localtime
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

    @freezegun.freeze_time("2023-11-6 13:00:00+03:00")
    def test_event_last_modified_time_is_updated_when_soft_delete(self):
        self.event_1.refresh_from_db()
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

        self.event_1.soft_delete()
        self.event_1.refresh_from_db()
        self.assertEqual(self.event_1.last_modified_time, timezone.now())

    @freezegun.freeze_time("2023-11-6 13:00:00+03:00")
    def test_event_last_modified_time_is_updated_when_undelete(self):
        self.event_1.deleted = True
        self.event_1.save(
            update_fields=["deleted"], skip_last_modified_time=True, force_update=True
        )
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

        self.event_1.undelete()
        self.event_1.refresh_from_db()
        self.assertEqual(self.event_1.last_modified_time, timezone.now())

    @freezegun.freeze_time("2023-11-6 13:00:00+03:00")
    def test_event_last_modified_time_is_update_when_queryset_soft_delete(self):
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

        Event.objects.filter(id=self.event_1.id).soft_delete()
        self.event_1.refresh_from_db()
        self.assertEqual(self.event_1.last_modified_time, timezone.now())

    @freezegun.freeze_time("2023-11-6 13:00:00+03:00")
    def test_event_last_modified_time_is_update_when_queryset_undelete(self):
        self.event_1.deleted = True
        self.event_1.save(
            update_fields=["deleted"], skip_last_modified_time=True, force_update=True
        )
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

        Event.objects.filter(id=self.event_1.id).undelete()
        self.event_1.refresh_from_db()
        self.assertEqual(self.event_1.last_modified_time, timezone.now())

    @freezegun.freeze_time("2023-11-6 13:00:00+03:00")
    def test_event_undelete_last_modified_time_is_not_updated_when_not_deleted(self):
        self.event_1.deleted = False
        self.event_1.save(
            update_fields=["deleted"], skip_last_modified_time=True, force_update=True
        )
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

        self.event_1.undelete()
        self.event_1.refresh_from_db()
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

    @freezegun.freeze_time("2023-11-6 13:00:00+03:00")
    def test_event_soft_delete_last_modified_time_is_not_updated_when_already_deleted(
        self,
    ):
        self.event_1.deleted = True
        self.event_1.save(
            update_fields=["deleted"], skip_last_modified_time=True, force_update=True
        )
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

        self.event_1.soft_delete()
        self.event_1.refresh_from_db()
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

    @freezegun.freeze_time("2023-11-6 13:00:00+03:00")
    def test_event_queryset_undelete_last_modified_time_is_not_updated_when_not_deleted(
        self,
    ):
        self.event_1.deleted = False
        self.event_1.save(
            update_fields=["deleted"], skip_last_modified_time=True, force_update=True
        )
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

        Event.objects.filter(id=self.event_1.id).undelete()
        self.event_1.refresh_from_db()
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

    @freezegun.freeze_time("2023-11-6 13:00:00+03:00")
    def test_event_queryset_soft_delete_last_modified_time_is_not_updated_when_already_deleted(
        self,
    ):
        self.event_1.deleted = True
        self.event_1.save(
            update_fields=["deleted"], skip_last_modified_time=True, force_update=True
        )
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

        Event.objects.filter(id=self.event_1.id).soft_delete()
        self.event_1.refresh_from_db()
        self.assertGreater(self.event_1.last_modified_time, timezone.now())

    @freezegun.freeze_time("2024-02-01 03:30:00+02:00")
    def test_event_get_start_and_end_time_display_both_times_given(self):
        self.event_1.start_time = localtime()
        self.event_1.end_time = self.event_1.start_time + timedelta(days=28)
        self.event_1.save(update_fields=["start_time", "end_time"])

        for lang, date_only, expected_time_display in (
            ("fi", False, "1.2.2024 klo 3:30 - 29.2.2024 klo 3:30"),
            ("fi", True, "1.2.2024 - 29.2.2024"),
            ("sv", False, "1.2.2024 kl. 3:30 - 29.2.2024 kl. 3:30"),
            ("sv", True, "1.2.2024 - 29.2.2024"),
            ("en", False, "1 Feb 2024 at 3:30 - 29 Feb 2024 at 3:30"),
            ("en", True, "1 Feb 2024 - 29 Feb 2024"),
        ):
            with self.subTest(), translation.override(lang):
                self.assertEqual(
                    self.event_1.get_start_and_end_time_display(
                        lang=lang, date_only=date_only
                    ),
                    expected_time_display,
                )

    @freezegun.freeze_time("2024-02-01 03:30:00+02:00")
    def test_event_get_start_and_end_time_display_start_time_given(self):
        self.event_1.start_time = localtime()
        self.event_1.save(update_fields=["start_time"])

        self.assertIsNone(self.event_1.end_time)

        for lang, date_only, expected_time_display in (
            ("fi", False, "1.2.2024 klo 3:30 -"),
            ("fi", True, "1.2.2024 -"),
            ("sv", False, "1.2.2024 kl. 3:30 -"),
            ("sv", True, "1.2.2024 -"),
            ("en", False, "1 Feb 2024 at 3:30 -"),
            ("en", True, "1 Feb 2024 -"),
        ):
            with self.subTest(), translation.override(lang):
                self.assertEqual(
                    self.event_1.get_start_and_end_time_display(
                        lang=lang, date_only=date_only
                    ),
                    expected_time_display,
                )

    @freezegun.freeze_time("2024-02-01 03:30:00+02:00")
    def test_event_get_start_and_end_time_display_end_time_given(self):
        self.event_1.end_time = localtime()
        self.event_1.save(update_fields=["end_time"])

        self.assertIsNone(self.event_1.start_time)

        for lang, date_only, expected_time_display in (
            ("fi", False, "- 1.2.2024 klo 3:30"),
            ("fi", True, "- 1.2.2024"),
            ("sv", False, "- 1.2.2024 kl. 3:30"),
            ("sv", True, "- 1.2.2024"),
            ("en", False, "- 1 Feb 2024 at 3:30"),
            ("en", True, "- 1 Feb 2024"),
        ):
            with self.subTest(), translation.override(lang):
                self.assertEqual(
                    self.event_1.get_start_and_end_time_display(
                        lang=lang, date_only=date_only
                    ),
                    expected_time_display,
                )

    @freezegun.freeze_time("2024-02-01 03:30:00+02:00")
    def test_event_get_start_and_end_time_display_both_times_missing(self):
        self.event_1.start_time = None
        self.event_1.end_time = None
        self.event_1.save(update_fields=["start_time", "end_time"])

        self.assertIsNone(self.event_1.start_time)
        self.assertIsNone(self.event_1.end_time)

        for lang, date_only, expected_time_display in (
            ("fi", False, ""),
            ("fi", True, ""),
            ("sv", False, ""),
            ("sv", True, ""),
            ("en", False, ""),
            ("en", True, ""),
        ):
            with self.subTest(), translation.override(lang):
                self.assertEqual(
                    self.event_1.get_start_and_end_time_display(
                        lang=lang, date_only=date_only
                    ),
                    expected_time_display,
                )


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
