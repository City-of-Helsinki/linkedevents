from django.contrib.auth import get_user_model
from django.test import TestCase

from events.models import Language
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationUserFactory,
    SignUpFactory,
)


class TestRegistration(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create(username="testuser")

        self.registration = RegistrationFactory()
        self.org = self.registration.event.publisher

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


class TestRegistrationUser(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create(username="testuser")

        self.registration = RegistrationFactory()
        self.org = self.registration.event.publisher
        self.registration_user = RegistrationUserFactory(
            registration=self.registration,
        )

    def test_can_be_edited_by_super_user(self):
        self.user.is_superuser = True
        self.user.save()

        can_be_edited = self.registration_user.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_cannot_be_edited_by_random_user(self):
        can_be_edited = self.registration_user.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_cannot_be_edited_by_regular_user(self):
        self.org.regular_users.add(self.user)

        can_be_edited = self.registration_user.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_can_be_edited_by_admin_user(self):
        self.org.admin_users.add(self.user)

        can_be_edited = self.registration_user.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)


class TestSignUp(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create(username="testuser")

        self.registration = RegistrationFactory()
        self.org = self.registration.event.publisher
        self.signup = SignUpFactory(
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
