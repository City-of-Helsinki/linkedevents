from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from registrations.admin import MandatoryFieldAdmin, RegistrationAdmin
from registrations.models import MandatoryField, Registration
from registrations.tests.factories import MandatoryFieldFactory, RegistrationFactory


def make_admin(username="testadmin", is_superuser=True):
    user_model = get_user_model()
    return user_model.objects.create(
        username=username, is_staff=True, is_superuser=is_superuser
    )


class TestRegistrationAdmin(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.registration = RegistrationFactory()

    def test_registrations_admin_is_registered(self):
        is_registered = admin.site.is_registered(Registration)
        self.assertTrue(is_registered)

    def test_readonly_fields(self):
        registration_admin = RegistrationAdmin(Registration, self.site)
        request = self.factory.get("/fake-url/")
        request.user = self.admin

        self.assertEquals(["id"], registration_admin.get_readonly_fields(request))
        self.assertEquals(
            ["id", "event"],
            registration_admin.get_readonly_fields(request, self.registration),
        )


class TestMandatoryFieldAdmin(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.deletable_mf = MandatoryFieldFactory(id="deletable")

    def test_mandatory_fields_admin_is_registered(self):
        is_registered = admin.site.is_registered(MandatoryField)
        self.assertTrue(is_registered)

    def test_has_delete_permission(self):
        mandatory_field_admin = MandatoryFieldAdmin(MandatoryField, self.site)
        request = self.factory.get("/fake-url/")
        request.user = self.admin
        qs = mandatory_field_admin.get_queryset(request)
        address_mf = qs.get(pk=MandatoryField.DefaultMandatoryField.ADDRESS)

        self.assertTrue(
            mandatory_field_admin.has_delete_permission(request, self.deletable_mf)
        )
        self.assertFalse(
            mandatory_field_admin.has_delete_permission(request, address_mf)
        )
        self.assertFalse(mandatory_field_admin.has_delete_permission(request, None))

    def test_readonly_fields(self):
        mandatory_field_admin = MandatoryFieldAdmin(MandatoryField, self.site)
        request = self.factory.get("/fake-url/")
        request.user = self.admin

        self.assertEquals([], mandatory_field_admin.get_readonly_fields(request))
        self.assertEquals(
            ["id"],
            mandatory_field_admin.get_readonly_fields(request, self.deletable_mf),
        )
