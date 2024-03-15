from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import override_settings, TestCase
from django_orghierarchy.models import Organization
from requests import RequestException
from rest_framework import status

from events.tests.factories import OrganizationFactory
from registrations.models import WebStoreMerchant
from registrations.tests.factories import WebStoreMerchantFactory
from web_store.tests.merchant.test_web_store_merchant_api_client import (
    DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
)
from web_store.tests.utils import get_mock_response


class LocalOrganizationAdminTestCaseMixin:
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = cls._create_admin_user("default")
        cls.site = AdminSite()
        cls.organization = OrganizationFactory()

    def setUp(self):
        self.client.force_login(self.admin_user)

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

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            data.update(
                {
                    "web_store_merchants-TOTAL_FORMS": "0",
                    "web_store_merchants-INITIAL_FORMS": "0",
                    "web_store_merchants-MIN_NUM_FORMS": "0",
                    "web_store_merchants-MAX_NUM_FORMS": "1",
                }
            )

        if update_data:
            data.update(update_data)

        return data


class TestLocalOrganizationAdmin(LocalOrganizationAdminTestCaseMixin, TestCase):
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

    def test_add_financial_admin_for_a_new_organization(self):
        self.assertEqual(Organization.objects.count(), 1)

        self.client.force_login(self.admin_user)
        data = self._get_request_data(
            {
                "name": "New Org",
                "internal_type": "normal",
                "financial_admin_users": [self.admin_user.pk],
            }
        )
        self.client.post(
            "/admin/django_orghierarchy/organization/add/",
            data,
        )

        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(
            Organization.objects.last().financial_admin_users.first().pk,
            self.admin_user.pk,
        )


class TestLocalOrganizationMerchantAdmin(LocalOrganizationAdminTestCaseMixin, TestCase):
    @staticmethod
    def _get_merchant_data(update_data=None):
        data = {
            "web_store_merchants-TOTAL_FORMS": "1",
            "web_store_merchants-INITIAL_FORMS": "0",
            "web_store_merchants-MIN_NUM_FORMS": "0",
            "web_store_merchants-MAX_NUM_FORMS": "1",
            "web_store_merchants-0-active": "on",
            "web_store_merchants-0-name": "Test Merchant",
            "web_store_merchants-0-street_address": "Street Address",
            "web_store_merchants-0-zipcode": "12345",
            "web_store_merchants-0-city": "Test City",
            "web_store_merchants-0-email": "test@test.dev",
            "web_store_merchants-0-phone_number": "+3580000000",
            "web_store_merchants-0-url": "https://test.dev/homepage/",
            "web_store_merchants-0-terms_of_service_url": "https://test.dev/terms_of_service/",
            "web_store_merchants-0-business_id": "1234567-8",
            "web_store_merchants-0-paytrail_merchant_id": "1234567",
        }

        if update_data:
            data.update(update_data)

        return data

    def assertMerchantValuesEqual(self, merchant, data, attrs_to_skip=None):
        attrs_to_skip = attrs_to_skip or []

        for field, value in data.items():
            if field.startswith("web_store_merchants-0-"):
                merchant_attr = field.split("-")[-1]
                if merchant_attr in attrs_to_skip:
                    continue

                if merchant_attr == "active":
                    merchant_value = True if value == "on" else False
                    getattr(self, f"assert{merchant_value}")(merchant.active)
                else:
                    self.assertEqual(getattr(merchant, merchant_attr), value)

    def assertMerchantValuesNotEqual(self, merchant, data, attrs_to_skip=None):
        attrs_to_skip = attrs_to_skip or []

        for field, value in data.items():
            if field.startswith("web_store_merchants-0-"):
                merchant_attr = field.split("-")[-1]
                if merchant_attr in attrs_to_skip:
                    continue

                if merchant_attr == "active":
                    merchant_value = False if value == "on" else True
                    getattr(self, f"assert{merchant_value}")(merchant.active)
                else:
                    self.assertNotEqual(getattr(merchant, merchant_attr), value)

    def test_can_add_web_store_merchant_to_a_new_organization(self):
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 0)

        data = self._get_request_data(
            {
                "name": "New Org",
                "internal_type": "normal",
                **self._get_merchant_data(),
            }
        )

        json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
        json_return_value["merchantId"] = "1234"
        mocked_create_merchant_response = get_mock_response(
            json_return_value=json_return_value,
        )
        with patch("requests.post") as mocked_create_merchant_request:
            mocked_create_merchant_request.return_value = (
                mocked_create_merchant_response
            )

            response = self.client.post(
                "/admin/django_orghierarchy/organization/add/",
                data,
            )
            self.assertEqual(response.status_code, status.HTTP_302_FOUND)
            self.assertTrue(mocked_create_merchant_request.called)

        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        merchant = WebStoreMerchant.objects.first()
        self.assertEqual(
            Organization.objects.last().web_store_merchants.first().pk,
            merchant.pk,
        )
        self.assertEqual(merchant.merchant_id, json_return_value["merchantId"])
        self.assertEqual(merchant.created_by_id, self.admin_user.pk)
        self.assertEqual(merchant.last_modified_by_id, self.admin_user.pk)
        self.assertIsNotNone(merchant.created_time)
        self.assertIsNotNone(merchant.last_modified_time)
        self.assertMerchantValuesEqual(merchant, data)

    def test_can_add_web_store_merchant_to_an_existing_organization(self):
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 0)

        merchant_data = self._get_merchant_data(
            update_data={"web_store_merchants-0-organization": self.organization.pk}
        )
        data = self._get_request_data(merchant_data)

        json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
        json_return_value["merchantId"] = "1234"
        mocked_create_merchant_response = get_mock_response(
            json_return_value=json_return_value,
        )
        with patch("requests.post") as mocked_create_merchant_request:
            mocked_create_merchant_request.return_value = (
                mocked_create_merchant_response
            )

            self.client.post(
                f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
                data,
            )
            self.assertTrue(mocked_create_merchant_request.called)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        merchant = WebStoreMerchant.objects.first()
        self.assertEqual(
            Organization.objects.first().web_store_merchants.first().pk,
            merchant.pk,
        )
        self.assertEqual(merchant.merchant_id, json_return_value["merchantId"])
        self.assertEqual(merchant.created_by_id, self.admin_user.pk)
        self.assertEqual(merchant.last_modified_by_id, self.admin_user.pk)
        self.assertIsNotNone(merchant.created_time)
        self.assertIsNotNone(merchant.last_modified_time)
        self.assertMerchantValuesEqual(merchant, data, attrs_to_skip=["organization"])

    def test_can_edit_web_store_merchant(self):
        with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
            # Don't do the full save() with the Talpa API call yet.
            merchant = WebStoreMerchantFactory(organization=self.organization)

        self.assertIsNotNone(merchant.created_time)
        self.assertIsNotNone(merchant.last_modified_time)
        merchant_last_modified_time = merchant.last_modified_time

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        merchant_data = self._get_merchant_data(
            update_data={
                "web_store_merchants-INITIAL_FORMS": "1",
                "web_store_merchants-0-id": merchant.pk,
                "web_store_merchants-0-organization": self.organization.pk,
                "web_store_merchants-0-name": "Edited Name",
            }
        )
        data = self._get_request_data(merchant_data)

        merchant_attrs_to_skip = ("id", "organization", "active")

        self.assertMerchantValuesNotEqual(
            merchant, data, attrs_to_skip=merchant_attrs_to_skip
        )

        json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
        json_return_value["merchantId"] = merchant.merchant_id
        mocked_update_merchant_response = get_mock_response(
            status_code=status.HTTP_200_OK,
            json_return_value=json_return_value,
        )
        with patch("requests.post") as mocked_update_merchant_request:
            mocked_update_merchant_request.return_value = (
                mocked_update_merchant_response
            )

            self.client.post(
                f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
                data,
            )
            self.assertTrue(mocked_update_merchant_request.called)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        self.organization.refresh_from_db()
        merchant.refresh_from_db()
        self.assertEqual(self.organization.web_store_merchants.first().pk, merchant.pk)
        self.assertEqual(merchant.last_modified_by_id, self.admin_user.pk)
        self.assertIsNotNone(merchant.created_time)
        self.assertIsNotNone(merchant.last_modified_time)
        self.assertTrue(merchant.last_modified_time > merchant_last_modified_time)
        self.assertMerchantValuesEqual(
            merchant, data, attrs_to_skip=merchant_attrs_to_skip
        )

    def test_cannot_add_web_store_merchant_without_all_required_fields(self):
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 0)

        for field in [
            "web_store_merchants-0-name",
            "web_store_merchants-0-street_address",
            "web_store_merchants-0-zipcode",
            "web_store_merchants-0-city",
            "web_store_merchants-0-email",
            "web_store_merchants-0-phone_number",
            "web_store_merchants-0-url",
            "web_store_merchants-0-terms_of_service_url",
            "web_store_merchants-0-business_id",
            "web_store_merchants-0-paytrail_merchant_id",
        ]:
            with self.subTest(), patch(
                "requests.post"
            ) as mocked_update_merchant_request:
                data = self._get_request_data(
                    {
                        "name": "New Org",
                        "internal_type": "normal",
                        **self._get_merchant_data(),
                    }
                )
                del data[field]

                self.client.post("/admin/django_orghierarchy/organization/add/", data)
                self.assertFalse(mocked_update_merchant_request.called)

                self.assertEqual(Organization.objects.count(), 1)
                self.assertEqual(WebStoreMerchant.objects.count(), 0)

    def test_cannot_delete_web_store_merchant(self):
        with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
            # Don't do the full save() with the Talpa API call.
            merchant = WebStoreMerchantFactory(organization=self.organization)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        merchant_data = self._get_merchant_data(
            update_data={
                "web_store_merchants-INITIAL_FORMS": "1",
                "web_store_merchants-0-id": merchant.pk,
                "web_store_merchants-0-organization": merchant.organization_id,
                "web_store_merchants-0-name": merchant.name,
                "web_store_merchants-0-street_address": merchant.street_address,
                "web_store_merchants-0-zipcode": merchant.zipcode,
                "web_store_merchants-0-city": merchant.city,
                "web_store_merchants-0-email": merchant.email,
                "web_store_merchants-0-phone_number": merchant.phone_number,
                "web_store_merchants-0-url": merchant.url,
                "web_store_merchants-0-terms_of_service_url": merchant.terms_of_service_url,
                "web_store_merchants-0-business_id": merchant.business_id,
                "web_store_merchants-0-paytrail_merchant_id": merchant.paytrail_merchant_id,
                "web_store_merchants-0-DELETE": "on",
            }
        )
        data = self._get_request_data(merchant_data)
        with patch("requests.post") as mocked_update_merchant_request:
            self.client.post(
                f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
                data,
            )
            self.assertFalse(mocked_update_merchant_request.called)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

    def test_add_web_store_merchant_to_a_new_organization_api_exception(self):
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 0)

        data = self._get_request_data(
            {
                "name": "New Org",
                "internal_type": "normal",
                **self._get_merchant_data(),
            }
        )

        mocked_create_merchant_response = get_mock_response(
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        with patch(
            "requests.post"
        ) as mocked_create_merchant_request, self.assertRaises(RequestException):
            mocked_create_merchant_request.return_value = (
                mocked_create_merchant_response
            )

            self.client.post(
                "/admin/django_orghierarchy/organization/add/",
                data,
            )
            self.assertTrue(mocked_create_merchant_request.called)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 0)

    def test_edit_web_store_merchant_api_exception(self):
        with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
            # Don't do the full save() with the Talpa API call yet.
            merchant = WebStoreMerchantFactory(organization=self.organization)
        merchant_last_modified_time = merchant.last_modified_time

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        merchant_data = self._get_merchant_data(
            update_data={
                "web_store_merchants-INITIAL_FORMS": "1",
                "web_store_merchants-0-id": merchant.pk,
                "web_store_merchants-0-organization": self.organization.pk,
                "web_store_merchants-0-name": "Edited Name",
            }
        )
        data = self._get_request_data(merchant_data)

        merchant_attrs_to_skip = ("id", "organization", "active")

        self.assertMerchantValuesNotEqual(
            merchant, data, attrs_to_skip=merchant_attrs_to_skip
        )

        mocked_update_merchant_response = get_mock_response(
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        with patch(
            "requests.post"
        ) as mocked_update_merchant_request, self.assertRaises(RequestException):
            mocked_update_merchant_request.return_value = (
                mocked_update_merchant_response
            )

            self.client.post(
                f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
                data,
            )
            self.assertTrue(mocked_update_merchant_request.called)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        merchant.refresh_from_db()
        self.assertMerchantValuesNotEqual(
            merchant, data, attrs_to_skip=merchant_attrs_to_skip
        )
        self.assertEqual(merchant_last_modified_time, merchant.last_modified_time)
