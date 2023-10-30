from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from events.models import Language
from events.tests.factories import DataSourceFactory, OrganizationFactory
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationUserAccessFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
)


class TestRegistration(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create(username="testuser")

        cls.data_source = DataSourceFactory(
            id="ds",
            name="data-source",
            api_key="test_api_key",
            user_editable_resources=True,
        )
        cls.org = OrganizationFactory(
            name="org",
            origin_id="org",
            data_source=cls.data_source,
        )

        cls.registration = RegistrationFactory(
            event__publisher=cls.org,
            event__data_source=cls.data_source,
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

    def test_can_be_edited_by_registration_admin_user(self):
        self.org.registration_admin_users.add(self.user)

        can_be_edited = self.registration.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)


class TestRegistrationUserAccess(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create(username="testuser")

        self.registration = RegistrationFactory()
        self.org = self.registration.event.publisher
        self.registration_user_access = RegistrationUserAccessFactory(
            registration=self.registration,
        )

    def test_can_be_edited_by_super_user(self):
        self.user.is_superuser = True
        self.user.save()

        can_be_edited = self.registration_user_access.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_cannot_be_edited_by_random_user(self):
        can_be_edited = self.registration_user_access.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_cannot_be_edited_by_regular_user(self):
        self.org.regular_users.add(self.user)

        can_be_edited = self.registration_user_access.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_can_be_edited_by_admin_user(self):
        self.org.admin_users.add(self.user)

        can_be_edited = self.registration_user_access.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)


class TestSignUpGroup(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create(username="testuser")

        cls.data_source = DataSourceFactory(
            id="ds",
            name="data-source",
            api_key="test_api_key",
            user_editable_resources=True,
        )

        cls.org = OrganizationFactory(
            name="org",
            origin_id="org",
            data_source=cls.data_source,
        )

        cls.signup_group = SignUpGroupFactory(
            registration__event__publisher=cls.org,
            registration__event__data_source=cls.data_source,
        )

    def test_can_be_edited_by_super_user(self):
        self.user.is_superuser = True
        self.user.save()

        can_be_edited = self.signup_group.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_cannot_be_edited_by_admin_user(self):
        self.org.admin_users.add(self.user)

        can_be_edited = self.signup_group.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_can_be_edited_by_registration_admin_user(self):
        self.org.registration_admin_users.add(self.user)

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
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create(username="testuser")

        cls.data_source = DataSourceFactory(
            id="ds",
            name="data-source",
            api_key="test_api_key",
            user_editable_resources=True,
        )
        cls.org = OrganizationFactory(
            name="org",
            origin_id="org",
            data_source=cls.data_source,
        )

        cls.signup = SignUpFactory(
            registration__event__publisher=cls.org,
            registration__event__data_source=cls.data_source,
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

    def test_cannot_be_edited_by_admin_user(self):
        self.org.admin_users.add(self.user)

        can_be_edited = self.signup.can_be_edited_by(self.user)
        self.assertFalse(can_be_edited)

    def test_can_be_edited_by_registration_admin_user(self):
        self.org.registration_admin_users.add(self.user)

        can_be_edited = self.signup.can_be_edited_by(self.user)
        self.assertTrue(can_be_edited)

    def test_full_name(self):
        for first_name, last_name, expected in (
            ("Firstname", "Lastname", "Firstname Lastname"),
            ("", "", ""),
            (" ", " ", ""),
            (None, None, ""),
            ("Firstname", "", "Firstname"),
            ("Firstname", None, "Firstname"),
            ("Firstname", " ", "Firstname"),
            ("", "Lastname", "Lastname"),
            (None, "Lastname", "Lastname"),
            (" ", "Lastname", "Lastname"),
        ):
            with self.subTest():
                self.signup.first_name = first_name
                self.signup.last_name = last_name
                self.signup.save(update_fields=["first_name", "last_name"])

                self.signup.refresh_from_db()

                self.assertEqual(self.signup.full_name, expected)

    def test_actual_contact_person_with_group(self):
        signup_group = SignUpGroupFactory(registration=self.signup.registration)
        contact_person = SignUpContactPersonFactory(signup_group=signup_group)
        self.signup.signup_group = signup_group
        self.signup.save(update_fields=["signup_group"])

        self.signup.refresh_from_db()

        assert self.signup.actual_contact_person.pk == contact_person.pk

    def test_actual_contact_person_without_group(self):
        contact_person = SignUpContactPersonFactory(signup=self.signup)

        self.signup.refresh_from_db()

        assert self.signup.actual_contact_person.pk == contact_person.pk


class TestSignUpContactPerson(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contact_person = SignUpContactPersonFactory(signup=SignUpFactory())

    def test_cannot_save_without_signup_or_signup_group(self):
        self.contact_person.signup = None

        with self.assertRaises(ValidationError):
            self.contact_person.save()

    def test_cannot_save_with_both_signup_and_signup_group(self):
        self.contact_person.signup_group = SignUpGroupFactory()

        with self.assertRaises(ValidationError):
            self.contact_person.save()

    def test_get_service_language_pk(self):
        sv = Language.objects.create(
            name="Swedish",
            pk="sv",
        )
        self.contact_person.service_language = sv
        self.contact_person.save(update_fields=["service_language"])

        self.assertEqual(self.contact_person.get_service_language_pk(), "sv")

    def test_get_default_service_language_pk(self):
        self.contact_person.service_language = None
        self.contact_person.save(update_fields=["service_language"])

        self.assertEqual(self.contact_person.get_service_language_pk(), "fi")

    def test_signup_registration(self):
        self.assertEqual(
            self.contact_person.registration.pk,
            self.contact_person.signup.registration_id,
        )

    def test_signup_group_registration(self):
        self.contact_person.signup = None
        self.contact_person.signup_group = SignUpGroupFactory()
        self.contact_person.save(update_fields=["signup", "signup_group"])

        self.assertEqual(
            self.contact_person.registration.pk,
            self.contact_person.signup_group.registration_id,
        )
