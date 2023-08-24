from django.contrib.auth import get_user_model
from django.test import TestCase
from django_orghierarchy.models import Organization

from events.models import DataSource, Event, Language
from registrations.models import Registration, SignUp, SignUpGroup


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


class TestSignUpGroup(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create(username="testuser")

        cls.data_source = DataSource.objects.create(
            id="ds",
            name="data-source",
            api_key="test_api_key",
            user_editable_resources=True,
        )

        cls.org = Organization.objects.create(
            name="org",
            origin_id="org",
            data_source=cls.data_source,
        )

        cls.event = Event.objects.create(
            id="ds:event",
            name="event",
            data_source=cls.data_source,
            publisher=cls.org,
        )

        cls.registration = Registration.objects.create(
            event=cls.event,
        )

        cls.signup_group = SignUpGroup.objects.create(registration=cls.registration)
        SignUp.objects.create(
            registration=cls.registration,
            signup_group=cls.signup_group,
        )

    def test_can_be_edited_by_super_user(self):
        self.user.is_superuser = True
        self.user.save()

        can_be_edited = self.signup_group.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_can_be_edited_by_admin_user(self):
        self.org.admin_users.add(self.user)

        can_be_edited = self.signup_group.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_can_be_edited_by_created_regular_user(self):
        self.org.regular_users.add(self.user)
        self.signup_group.created_by = self.user
        self.signup_group.save(update_fields=["created_by"])

        can_be_edited = self.signup_group.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_cannot_be_edited_by_non_created_regular_user(self):
        self.org.regular_users.add(self.user)

        can_be_edited = self.signup_group.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_get_publisher(self):
        self.assertEqual(self.signup_group.publisher.id, self.org.id)

    def test_get_data_source(self):
        self.assertEqual(self.signup_group.data_source.id, self.data_source.id)


class TestSignUp(TestCase):
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
        self.signup = SignUp.objects.create(
            registration=self.registration,
        )

    def test_can_be_edited_by_super_user(self):
        self.user.is_superuser = True
        self.user.save()

        can_be_edited = self.signup.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_cannot_be_edited_by_random_user(self):
        can_be_edited = self.signup.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_cannot_be_edited_by_regular_user(self):
        self.org.regular_users.add(self.user)

        can_be_edited = self.signup.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_can_be_edited_by_admin_user(self):
        self.org.admin_users.add(self.user)

        can_be_edited = self.signup.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_get_service_language_pk(self):
        sv = Language.objects.create(
            name="Swedish",
            pk="sv",
        )
        self.signup.service_language = sv
        self.signup.save()

        self.assertEqual(self.signup.get_service_language_pk(), "sv")

    def test_get_default_service_language_pk(self):
        self.signup.service_language = None
        self.signup.save()

        self.assertEqual(self.signup.get_service_language_pk(), "fi")
