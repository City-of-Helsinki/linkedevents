from django.test import TestCase
from django_orghierarchy.models import Organization

from events.models import DataSource
from registrations.tests.factories import RegistrationUserAccessFactory
from registrations.tests.test_registration_post import hel_email

from ..models import User


class TestUser(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="testuser")
        data_source = DataSource.objects.create(id="ds", name="data-source")

        self.org_1 = Organization.objects.create(
            data_source=data_source,
            origin_id="org-1",
        )
        self.org_2 = Organization.objects.create(
            data_source=data_source,
            origin_id="org-2",
            replaced_by=self.org_1,
        )
        self.org = Organization.objects.create(
            name="org",
            origin_id="org",
            data_source=data_source,
        )
        self.child_org = Organization.objects.create(
            name="child-org",
            origin_id="child-org",
            data_source=data_source,
            parent=self.org,
        )
        self.affiliated_org = Organization.objects.create(
            name="affiliated-org",
            origin_id="affiliated-org",
            data_source=data_source,
            parent=self.org,
            internal_type=Organization.AFFILIATED,
        )

    def test_get_default_organization(self):
        self.org_1.admin_users.add(self.user)
        org = self.user.get_default_organization()
        self.assertEqual(org, self.org_1)

    def test_get_default_organization_org_replaced(self):
        self.org_2.admin_users.add(self.user)
        org = self.user.get_default_organization()
        self.assertIsNone(org)

    def test_is_admin(self):
        self.org.admin_users.add(self.user)

        # test for admin organization
        is_admin = self.user.is_admin_of(self.org)
        self.assertTrue(is_admin)

        # test for child organization
        is_admin = self.user.is_admin_of(self.child_org)
        self.assertTrue(is_admin)

        # test for affiliated organization
        is_admin = self.user.is_admin_of(self.affiliated_org)
        self.assertTrue(is_admin)

        # test for some other organization
        is_admin = self.user.is_admin_of(self.org_1)
        self.assertFalse(is_admin)

    def test_is_registration_admin(self):
        self.org.registration_admin_users.add(self.user)

        # test for admin organization
        is_registration_admin = self.user.is_registration_admin_of(self.org)
        self.assertTrue(is_registration_admin)

        # test for child organization
        is_registration_admin = self.user.is_registration_admin_of(self.child_org)
        self.assertTrue(is_registration_admin)

        # test for affiliated organization
        is_registration_admin = self.user.is_registration_admin_of(self.affiliated_org)
        self.assertTrue(is_registration_admin)

        # test for some other organization
        is_registration_admin = self.user.is_registration_admin_of(self.org_1)
        self.assertFalse(is_registration_admin)

    def test_is_financial_admin(self):
        self.org.financial_admin_users.add(self.user)

        # test for admin organization
        is_financial_admin = self.user.is_financial_admin_of(self.org)
        self.assertTrue(is_financial_admin)

        # test for child organization
        is_financial_admin = self.user.is_financial_admin_of(self.child_org)
        self.assertTrue(is_financial_admin)

        # test for affiliated organization
        is_financial_admin = self.user.is_financial_admin_of(self.affiliated_org)
        self.assertTrue(is_financial_admin)

        # test for some other organization
        is_financial_admin = self.user.is_financial_admin_of(self.org_1)
        self.assertFalse(is_financial_admin)

        # test for no organization
        is_financial_admin = self.user.is_financial_admin_of(None)
        self.assertFalse(is_financial_admin)

    def test_is_regular_user(self):
        self.org.regular_users.add(self.user)

        # test for admin organization
        is_admin = self.user.is_admin_of(self.org)
        self.assertFalse(is_admin)
        is_regular_user = self.user.is_regular_user_of(self.org)
        self.assertTrue(is_regular_user)

        # test for child organization
        is_admin = self.user.is_admin_of(self.child_org)
        self.assertFalse(is_admin)
        is_regular_user = self.user.is_regular_user_of(self.child_org)
        self.assertFalse(is_regular_user)

        # test for affiliated organization
        is_admin = self.user.is_admin_of(self.affiliated_org)
        self.assertFalse(is_admin)
        is_regular_user = self.user.is_regular_user_of(self.affiliated_org)
        self.assertFalse(is_regular_user)

        # test for some other organization
        is_admin = self.user.is_admin_of(self.org_1)
        self.assertFalse(is_admin)
        is_regular_user = self.user.is_regular_user_of(self.org_1)
        self.assertFalse(is_regular_user)

    def test_is_substitute_user(self):
        self.org.regular_users.add(self.user)
        self.user.email = hel_email
        self.user.save(update_fields=["email"])

        # User has correct email and a substitute user access exists.
        substitute_user_access = RegistrationUserAccessFactory(
            email=hel_email, is_substitute_user=True
        )
        self.assertTrue(self.user.is_substitute_user)

        # User has correct email, but a substitute user access is not granted.
        substitute_user_access.is_substitute_user = False
        substitute_user_access.save(update_fields=["is_substitute_user"])
        del self.user.is_substitute_user
        self.assertFalse(self.user.is_substitute_user)

        # User has wrong email while a substitute user access exists.
        substitute_user_access.is_substitute_user = True
        substitute_user_access.save(update_fields=["is_substitute_user"])
        self.user.email = "wrong@test.dev"
        self.user.save(update_fields=["email"])
        del self.user.is_substitute_user
        self.assertFalse(self.user.is_substitute_user)

        # User does not have substitute user access.
        substitute_user_access.delete()
        self.user.email = hel_email
        self.user.save(update_fields=["email"])
        del self.user.is_substitute_user
        self.assertFalse(self.user.is_substitute_user)
