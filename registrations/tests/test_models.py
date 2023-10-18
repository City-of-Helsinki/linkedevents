from django.contrib.auth import get_user_model
from django.test import TestCase

from events.models import Language
from events.tests.factories import DataSourceFactory, OrganizationFactory
from helevents.tests.factories import UserFactory
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationUserAccessFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpGroupProtectedDataFactory,
    SignUpProtectedDataFactory,
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

    def test_signup_group_data_is_pseudonymised(self):
        registration = RegistrationFactory()
        user = UserFactory()
        signup_group = SignUpGroupFactory(
            registration=registration,
            created_by=user,
            last_modified_by=user,
        )
        SignUpGroupProtectedDataFactory(
            signup_group=signup_group,
            registration=registration,
            extra_info="Group extra info",
        )
        signup = SignUpFactory(
            registration=registration,
            created_by=user,
            last_modified_by=user,
            email="test@email.com",
            membership_number="xxx",
            phone_number="044 1234567",
            street_address="Street address 12",
            first_name="First name",
            last_name="Last name",
            signup_group=signup_group,
        )
        SignUpProtectedDataFactory(
            signup=signup,
            registration=registration,
            extra_info="Extra info",
            date_of_birth="2012-12-12",
        )

        assert signup_group.pseudonymization_time is None
        assert signup_group.created_by == user
        assert signup_group.last_modified_by == user
        assert signup.pseudonymization_time is None
        assert signup.created_by == user
        assert signup.last_modified_by == user

        signup_group.pseudonymize()

        assert signup_group.extra_info == "c162ac0d09c95f4a"
        assert signup_group.pseudonymization_time is not None
        assert signup_group.created_by is None
        assert signup_group.last_modified_by is None

        signup.refresh_from_db()
        assert signup.email == "5970@709281.fi"
        assert signup.membership_number == "095"
        assert signup.phone_number == "0712923071"
        assert signup.street_address == "Ee327f2d263567 97"
        assert signup.first_name == "F8b44f018d"
        assert signup.last_name == "0dd585045"
        assert signup.extra_info == "5592136a3c"
        assert str(signup.date_of_birth) == "6530-12-24"
        assert signup.pseudonymization_time is not None
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

    def test_signup_data_is_pseudonymised(self):
        user = UserFactory()
        signup = SignUpFactory(
            created_by=user,
            last_modified_by=user,
            email="test@email.com",
            membership_number="xxx",
            phone_number="044 1234567",
            street_address="Street address 12",
            first_name="First name",
            last_name="Last name",
        )
        SignUpProtectedDataFactory(
            signup=signup,
            registration=signup.registration,
            extra_info="Extra info",
            date_of_birth="2012-12-12",
        )

        assert signup.pseudonymization_time is None
        assert signup.created_by == user
        assert signup.last_modified_by == user

        signup.pseudonymize()

        assert signup.email == "5970@709281.fi"
        assert signup.membership_number == "095"
        assert signup.phone_number == "0712923071"
        assert signup.street_address == "Ee327f2d263567 97"
        assert signup.first_name == "F8b44f018d"
        assert signup.last_name == "0dd585045"
        assert signup.extra_info == "5592136a3c"
        assert signup.date_of_birth == "6530-12-24"
        assert signup.pseudonymization_time is not None
        assert signup.created_by is None
        assert signup.last_modified_by is None
