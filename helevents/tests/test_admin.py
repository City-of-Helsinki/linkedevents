from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django_orghierarchy.forms import OrganizationForm
from django_orghierarchy.models import Organization

from events.tests.factories import OrganizationFactory


class TestLocalOrganizationAdmin(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.admin = user_model.objects.create(
            username="testadmin",
            is_staff=True,
            is_superuser=True,
        )
        cls.request_factory = RequestFactory()
        cls.site = AdminSite()
        cls.organization = OrganizationFactory()

    def test_organization_admin_is_registered(self):
        is_registered = admin.site.is_registered(Organization)
        self.assertTrue(is_registered)

    def test_add_registration_admin(self):
        self.assertEqual(self.organization.registration_admin_users.count(), 0)

        self.client.force_login(self.admin)

        data = OrganizationForm(instance=self.organization).initial
        for key, value in data.items():
            if value is None:
                data[key] = ""
        data["registration_admin_users"] = [self.admin.pk]
        self.client.post(
            f"/admin/django_orghierarchy/organization/{self.organization.pk}/change/",
            data,
        )

        self.organization.refresh_from_db()
        # self.assertEqual(self.organization.registration_admin_users.count(), 1)
        # self.assertEqual(self.organization.registration_admin_users.first().pk, self.admin.pk)
