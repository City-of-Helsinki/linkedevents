import pytest
from django.test import TestCase
from django_orghierarchy.models import Organization

from events.models import DataSource

from ..models import User


@pytest.mark.no_test_audit_log
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
