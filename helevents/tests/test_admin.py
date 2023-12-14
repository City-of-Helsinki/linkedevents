from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import TestCase
from django_orghierarchy.models import Organization
from rest_framework import status

from events.tests.factories import OrganizationFactory


class TestLocalOrganizationAdmin(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = cls._create_admin_user("default")
        cls.site = AdminSite()
        cls.organization = OrganizationFactory()

    @staticmethod
    def _create_admin_user(username, is_staff=True, is_superuser=True):
        user_model = get_user_model()
        return user_model.objects.create(
            username=username,
            is_staff=is_staff,
            is_superuser=is_superuser,
        )

    @staticmethod
    def _get_request_data(update_data=None):
        data = {
            "children-TOTAL_FORMS": 0,
            "children-INITIAL_FORMS": 0,
            "children-MIN_NUM_FORMS": 0,
            "children-MAX_NUM_FORMS": 0,
            "children-2-TOTAL_FORMS": 0,
            "children-2-INITIAL_FORMS": 0,
            "children-3-TOTAL_FORMS": 0,
            "children-3-INITIAL_FORMS": 0,
            "children-4-TOTAL_FORMS": 0,
            "children-4-INITIAL_FORMS": 0,
            "children-5-TOTAL_FORMS": 0,
            "children-5-INITIAL_FORMS": 0,
            "children-6-TOTAL_FORMS": 0,
            "children-6-INITIAL_FORMS": 0,
        }
        if update_data:
            data.update(update_data)
        return data

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_organization_admin_is_registered(self):
        is_registered = admin.site.is_registered(Organization)
        self.assertTrue(is_registered)

    def test_add_registration_admin(self):
        self.assertEqual(self.organization.registration_admin_users.count(), 0)

        data = self._get_request_data(
            {"registration_admin_users": [self.admin_user.pk]}
        )
        self.client.post(
            f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
            data,
        )

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.registration_admin_users.count(), 1)
        self.assertEqual(
            self.organization.registration_admin_users.first().pk, self.admin_user.pk
        )

    def test_add_multiple_registration_admins(self):
        self.assertEqual(self.organization.registration_admin_users.count(), 0)

        admin_user2 = self._create_admin_user("admin 2")
        data = self._get_request_data(
            {"registration_admin_users": [self.admin_user.pk, admin_user2.pk]}
        )
        self.client.post(
            f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
            data,
        )

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.registration_admin_users.count(), 2)

    def test_remove_registration_admin(self):
        admin_user2 = self._create_admin_user("admin 2")
        self.organization.registration_admin_users.set([self.admin_user, admin_user2])

        self.assertEqual(self.organization.registration_admin_users.count(), 2)

        data = self._get_request_data(
            {"registration_admin_users": [self.admin_user.pk]}
        )
        self.client.post(
            f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
            data,
        )

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.registration_admin_users.count(), 1)
        self.assertEqual(
            self.organization.registration_admin_users.first().pk, self.admin_user.pk
        )

    def test_add_registration_admin_for_a_new_organization(self):
        self.assertEqual(Organization.objects.count(), 1)

        data = self._get_request_data(
            {
                "name": "New Org",
                "internal_type": "normal",
                "registration_admin_users": [self.admin_user.pk],
            }
        )
        response = self.client.post(
            "/admin/django_orghierarchy/organization/add/",
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(
            Organization.objects.last().registration_admin_users.first().pk,
            self.admin_user.pk,
        )

    def test_add_financial_admin(self):
        self.assertEqual(self.organization.financial_admin_users.count(), 0)

        self.client.force_login(self.admin_user)
        data = self._get_request_data({"financial_admin_users": [self.admin_user.pk]})
        self.client.post(
            f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
            data,
        )

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.financial_admin_users.count(), 1)
        self.assertEqual(
            self.organization.financial_admin_users.first().pk, self.admin_user.pk
        )

    def test_add_multiple_financial_admins(self):
        self.assertEqual(self.organization.financial_admin_users.count(), 0)

        self.client.force_login(self.admin_user)
        admin_user2 = self._create_admin_user("admin 2")
        data = self._get_request_data(
            {"financial_admin_users": [self.admin_user.pk, admin_user2.pk]}
        )
        self.client.post(
            f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
            data,
        )

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.financial_admin_users.count(), 2)

    def test_remove_financial_admin(self):
        admin_user2 = self._create_admin_user("admin 2")
        self.organization.financial_admin_users.set([self.admin_user, admin_user2])

        self.assertEqual(self.organization.financial_admin_users.count(), 2)

        self.client.force_login(self.admin_user)
        data = self._get_request_data({"financial_admin_users": [self.admin_user.pk]})
        self.client.post(
            f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
            data,
        )

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.financial_admin_users.count(), 1)
        self.assertEqual(
            self.organization.financial_admin_users.first().pk, self.admin_user.pk
        )
