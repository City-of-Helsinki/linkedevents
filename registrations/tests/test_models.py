from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from events.models import Language
from events.tests.factories import DataSourceFactory, OrganizationFactory
from helevents.tests.factories import UserFactory
from registrations.models import RegistrationPriceGroup
from registrations.notifications import SignUpNotificationType
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpGroupProtectedDataFactory,
    SignUpProtectedDataFactory,
)

contact_person_data = {
    "email": "test@email.com",
    "first_name": "Contact first name",
    "last_name": "Contact last name",
    "membership_number": "xxx",
    "phone_number": "044 1234567",
}

signup_group_data = {"protected_data": {"extra_info": "Group extra info"}}

signup_data = {
    "city": "City",
    "first_name": "First name",
    "last_name": "Last name",
    "street_address": "Street address 12",
    "zipcode": "12345",
    "protected_data": {
        "date_of_birth": "2012-12-12",
        "extra_info": "Extra info",
    },
}

anonymize_replacement = "<DELETED>"


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

    def test_signup_group_data_is_anonymized(self):
        registration = RegistrationFactory()
        user = UserFactory()
        signup_group = SignUpGroupFactory(
            registration=registration,
            created_by=user,
            last_modified_by=user,
        )
        signup_group_protected_data = SignUpGroupProtectedDataFactory(
            signup_group=signup_group,
            registration=registration,
            extra_info=signup_group_data["protected_data"]["extra_info"],
        )
        contact_person = SignUpContactPersonFactory(
            signup_group=signup_group,
            email=contact_person_data["email"],
            first_name=contact_person_data["first_name"],
            last_name=contact_person_data["last_name"],
            membership_number=contact_person_data["membership_number"],
            phone_number=contact_person_data["phone_number"],
        )
        signup = SignUpFactory(
            created_by=user,
            last_modified_by=user,
            street_address=signup_data["street_address"],
            city=signup_data["city"],
            zipcode=signup_data["zipcode"],
            first_name=signup_data["first_name"],
            last_name=signup_data["last_name"],
            registration=registration,
            signup_group=signup_group,
        )
        signup_protected_data = SignUpProtectedDataFactory(
            signup=signup,
            registration=signup.registration,
            date_of_birth=signup_data["protected_data"]["date_of_birth"],
            extra_info=signup_data["protected_data"]["extra_info"],
        )

        assert signup_group.anonymization_time is None
        assert signup_group.created_by == user
        assert signup_group.last_modified_by == user
        assert signup.anonymization_time is None
        assert signup.created_by == user
        assert signup.last_modified_by == user

        signup_group.anonymize()

        # Signup group should be anonymized
        assert signup_group_protected_data.extra_info == anonymize_replacement
        assert contact_person.email == anonymize_replacement
        assert contact_person.first_name == anonymize_replacement
        assert contact_person.last_name == anonymize_replacement
        assert contact_person.membership_number == anonymize_replacement
        assert contact_person.phone_number == anonymize_replacement
        assert signup_group.anonymization_time is not None
        assert signup_group.created_by is None
        assert signup_group.last_modified_by is None

        # Signup should be anonymized
        signup.refresh_from_db()
        signup_protected_data.refresh_from_db()
        # City and zipcode are not anonymized
        assert signup.city == signup_data["city"]
        assert signup.zipcode == signup_data["zipcode"]
        # All other signup fields are anonymized
        assert signup.first_name == anonymize_replacement
        assert signup.last_name == anonymize_replacement
        assert signup.street_address == anonymize_replacement
        # Date of birth is not anonymized
        assert (
            str(signup_protected_data.date_of_birth)
            == signup_data["protected_data"]["date_of_birth"]
        )
        # Extra info is anonymized
        assert signup_protected_data.extra_info == anonymize_replacement
        assert signup.anonymization_time is not None
        assert signup.created_by is None
        assert signup.last_modified_by is None


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

    def test_signup_data_is_anonymisized(self):
        user = UserFactory()
        signup = SignUpFactory(
            created_by=user,
            last_modified_by=user,
            street_address=signup_data["street_address"],
            city=signup_data["city"],
            zipcode=signup_data["zipcode"],
            first_name=signup_data["first_name"],
            last_name=signup_data["last_name"],
        )
        contact_person = SignUpContactPersonFactory(
            signup=signup,
            email=contact_person_data["email"],
            first_name=contact_person_data["first_name"],
            last_name=contact_person_data["last_name"],
            membership_number=contact_person_data["membership_number"],
            phone_number=contact_person_data["phone_number"],
        )
        protected_data = SignUpProtectedDataFactory(
            signup=signup,
            registration=signup.registration,
            date_of_birth=signup_data["protected_data"]["date_of_birth"],
            extra_info=signup_data["protected_data"]["extra_info"],
        )

        assert signup.anonymization_time is None
        assert signup.created_by == user
        assert signup.last_modified_by == user

        signup.anonymize()

        # City and zipcode are not anonymized
        assert signup.city == signup_data["city"]
        assert signup.zipcode == signup_data["zipcode"]
        # All other signup fields are anonymized
        assert signup.first_name == anonymize_replacement
        assert signup.last_name == anonymize_replacement
        assert signup.street_address == anonymize_replacement
        # All contact person fields are anonymized
        assert contact_person.email == anonymize_replacement
        assert contact_person.first_name == anonymize_replacement
        assert contact_person.last_name == anonymize_replacement
        assert contact_person.membership_number == anonymize_replacement
        assert contact_person.phone_number == anonymize_replacement
        # Date of birth is not anonymized
        assert (
            str(protected_data.date_of_birth)
            == signup_data["protected_data"]["date_of_birth"]
        )
        # Extra info is anonymized
        assert protected_data.extra_info == anonymize_replacement
        assert signup.anonymization_time is not None
        assert signup.created_by is None
        assert signup.last_modified_by is None


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

    def test_send_notification(self):
        self.contact_person.email = "test@test.dev"
        self.contact_person.save(update_fields=["email"])

        for notification_type in (
            SignUpNotificationType.EVENT_CANCELLATION,
            SignUpNotificationType.CANCELLATION,
            SignUpNotificationType.CONFIRMATION,
            SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST,
            SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT,
        ):
            with self.subTest():
                self.contact_person.send_notification(notification_type)

                self.assertEqual(len(mail.outbox), 1)
                self.assertEqual(mail.outbox[0].to[0], self.contact_person.email)

                mail.outbox.clear()

    def test_send_notification_unknown_notification_type(self):
        self.contact_person.email = "test@test.dev"
        self.contact_person.save(update_fields=["email"])

        with self.assertRaises(ValueError):
            self.contact_person.send_notification("does-not-exist")

        self.assertEqual(len(mail.outbox), 0)


class TestRegistrationPriceGroup(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.registration_price_group = RegistrationPriceGroupFactory()

    def test_calculate_vat_and_price_without_vat(self):
        self.registration_price_group.price = Decimal("324")
        self.registration_price_group.vat_percentage = (
            RegistrationPriceGroup.VatPercentage.VAT_24
        )

        self.assertEquals(self.registration_price_group.price_without_vat, Decimal("0"))
        self.assertEquals(self.registration_price_group.vat, Decimal("0"))

        self.registration_price_group.calculate_vat_and_price_without_vat()

        self.assertEquals(
            self.registration_price_group.price_without_vat, Decimal("261.29")
        )
        self.assertEquals(self.registration_price_group.vat, Decimal("62.71"))
