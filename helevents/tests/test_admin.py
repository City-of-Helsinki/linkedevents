import re
from copy import deepcopy

import requests_mock
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import TestCase
from django_orghierarchy.models import Organization
from rest_framework import status

from events.tests.factories import OrganizationFactory
from registrations.exceptions import WebStoreAPIError
from registrations.models import WebStoreAccount, WebStoreMerchant
from registrations.tests.factories import (
    WebStoreAccountFactory,
    WebStoreMerchantFactory,
)
from web_store.tests.merchant.test_web_store_merchant_api_client import (
    DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
    DEFAULT_MERCHANT_ID,
)


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
                    "web_store_accounts-TOTAL_FORMS": "0",
                    "web_store_accounts-INITIAL_FORMS": "0",
                    "web_store_accounts-MIN_NUM_FORMS": "0",
                    "web_store_accounts-MAX_NUM_FORMS": "1",
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
    _MERCHANT_ATTR_RE = re.compile(r"web_store_merchants-\d+-(\w+)")

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
            if match := re.match(self._MERCHANT_ATTR_RE, field):
                merchant_attr = match.group(1)
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
            if match := re.match(self._MERCHANT_ATTR_RE, field):
                merchant_attr = match.group(1)
                if merchant_attr in attrs_to_skip:
                    continue

                if merchant_attr == "active":
                    merchant_value = False if value == "on" else True
                    getattr(self, f"assert{merchant_value}")(merchant.active)
                else:
                    self.assertNotEqual(getattr(merchant, merchant_attr), value)

    def test_can_add_web_store_merchants_to_a_new_organization(self):
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 0)

        merchant_data = self._get_merchant_data()
        merchant_data2 = {
            "web_store_merchants-TOTAL_FORMS": "2",
            "web_store_merchants-1-active": "on",
            "web_store_merchants-1-name": "Test Merchant 2",
            "web_store_merchants-1-street_address": "Street Address 2",
            "web_store_merchants-1-zipcode": "54321",
            "web_store_merchants-1-city": "Test City 2",
            "web_store_merchants-1-email": "test2@test.dev",
            "web_store_merchants-1-phone_number": "+3581111111",
            "web_store_merchants-1-terms_of_service_url": "https://test.com/terms_of_service/",
            "web_store_merchants-1-business_id": "1234567-9",
            "web_store_merchants-1-paytrail_merchant_id": "7654321",
        }
        data = self._get_request_data(
            {
                "name": "New Org",
                "internal_type": "normal",
            }
        )
        data.update(merchant_data)
        data.update(merchant_data2)

        json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
        json_return_value["merchantId"] = "1234"

        json_return_value2 = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
        json_return_value2["merchantId"] = "4321"

        def merchant2_matcher(request):
            return (
                request.json()["merchantName"]
                == merchant_data2["web_store_merchants-1-name"]
            )

        with requests_mock.Mocker() as req_mock:
            merchant_create_url = (
                f"{settings.WEB_STORE_API_BASE_URL}merchant/create/"
                f"merchant/{settings.WEB_STORE_API_NAMESPACE}"
            )
            req_mock.post(
                merchant_create_url,
                json=json_return_value,
            )
            req_mock.post(
                merchant_create_url,
                json=json_return_value2,
                additional_matcher=merchant2_matcher,
            )

            response = self.client.post(
                "/admin/django_orghierarchy/organization/add/",
                data,
            )
            self.assertEqual(response.status_code, status.HTTP_302_FOUND)

            self.assertEqual(req_mock.call_count, 2)

        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(WebStoreMerchant.objects.count(), 2)

        organization = Organization.objects.last()
        for merchant_id, merchant_data in [
            (json_return_value["merchantId"], merchant_data),
            (json_return_value2["merchantId"], merchant_data2),
        ]:
            merchant = WebStoreMerchant.objects.get(
                merchant_id=merchant_id,
                organization_id=organization.pk,
                created_by_id=self.admin_user.pk,
                last_modified_by_id=self.admin_user.pk,
            )
            self.assertIsNotNone(merchant.created_time)
            self.assertIsNotNone(merchant.last_modified_time)

            merchant_data["url"] = settings.LINKED_EVENTS_UI_URL
            self.assertMerchantValuesEqual(merchant, merchant_data)

    def test_can_add_web_store_merchant_to_an_existing_organization(self):
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 0)

        merchant_data = self._get_merchant_data(
            update_data={"web_store_merchants-0-organization": self.organization.pk}
        )
        data = self._get_request_data(merchant_data)

        with requests_mock.Mocker() as req_mock:
            req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}merchant/create/"
                f"merchant/{settings.WEB_STORE_API_NAMESPACE}",
                json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
            )

            self.client.post(
                f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
                data,
            )

            self.assertEqual(req_mock.call_count, 1)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        merchant = WebStoreMerchant.objects.first()
        self.assertEqual(
            Organization.objects.first().web_store_merchants.first().pk,
            merchant.pk,
        )
        self.assertEqual(merchant.merchant_id, DEFAULT_MERCHANT_ID)
        self.assertEqual(merchant.created_by_id, self.admin_user.pk)
        self.assertEqual(merchant.last_modified_by_id, self.admin_user.pk)
        self.assertIsNotNone(merchant.created_time)
        self.assertIsNotNone(merchant.last_modified_time)

        data["url"] = settings.LINKED_EVENTS_UI_URL
        self.assertMerchantValuesEqual(merchant, data, attrs_to_skip=["organization"])

    def test_can_edit_web_store_merchant(self):
        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            # Don't do the full save() with the Talpa API call yet.
            merchant = WebStoreMerchantFactory(
                organization=self.organization,
                merchant_id=DEFAULT_MERCHANT_ID,
                paytrail_merchant_id="1234567",
            )

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

        merchant_attrs_to_skip = (
            "id",
            "organization",
            "active",
            "paytrail_merchant_id",
        )

        self.assertMerchantValuesNotEqual(
            merchant, data, attrs_to_skip=merchant_attrs_to_skip
        )

        with requests_mock.Mocker() as req_mock:
            req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}merchant/update/"
                f"merchant/{settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}",
                json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
            )

            self.client.post(
                f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
                data,
            )
            self.assertEqual(req_mock.call_count, 1)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        self.organization.refresh_from_db()
        merchant.refresh_from_db()
        self.assertEqual(self.organization.web_store_merchants.first().pk, merchant.pk)
        self.assertEqual(merchant.last_modified_by_id, self.admin_user.pk)
        self.assertIsNotNone(merchant.created_time)
        self.assertIsNotNone(merchant.last_modified_time)
        self.assertTrue(merchant.last_modified_time > merchant_last_modified_time)

        data["url"] = settings.LINKED_EVENTS_UI_URL
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
            "web_store_merchants-0-terms_of_service_url",
            "web_store_merchants-0-business_id",
            "web_store_merchants-0-paytrail_merchant_id",
        ]:
            with (
                self.subTest(),
                requests_mock.Mocker() as req_mock,
            ):
                req_mock.post(
                    f"{settings.WEB_STORE_API_BASE_URL}merchant/create/"
                    f"merchant/{settings.WEB_STORE_API_NAMESPACE}",
                )

                data = self._get_request_data(
                    {
                        "name": "New Org",
                        "internal_type": "normal",
                        **self._get_merchant_data(),
                    }
                )
                del data[field]

                self.client.post("/admin/django_orghierarchy/organization/add/", data)

                self.assertEqual(req_mock.call_count, 0)

                self.assertEqual(Organization.objects.count(), 1)
                self.assertEqual(WebStoreMerchant.objects.count(), 0)

    def test_cannot_delete_web_store_merchant(self):
        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
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
                "web_store_merchants-0-terms_of_service_url": merchant.terms_of_service_url,
                "web_store_merchants-0-business_id": merchant.business_id,
                "web_store_merchants-0-paytrail_merchant_id": merchant.paytrail_merchant_id,
                "web_store_merchants-0-DELETE": "on",
            }
        )
        data = self._get_request_data(merchant_data)
        with requests_mock.Mocker() as req_mock:
            req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}create/merchant/"
                f"merchant/{settings.WEB_STORE_API_NAMESPACE}",
            )
            req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}update/merchant/"
                f"merchant/{settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}",
            )

            self.client.post(
                f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
                data,
            )

            self.assertEqual(req_mock.call_count, 0)

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

        with (
            requests_mock.Mocker() as req_mock,
            self.assertRaises(WebStoreAPIError),
        ):
            req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}merchant/create/"
                f"merchant/{settings.WEB_STORE_API_NAMESPACE}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

            self.client.post(
                "/admin/django_orghierarchy/organization/add/",
                data,
            )

            self.assertEqual(req_mock.call_count, 1)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 0)

    def test_edit_web_store_merchant_api_exception(self):
        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            # Don't do the full save() with the Talpa API call yet.
            merchant = WebStoreMerchantFactory(
                organization=self.organization,
                merchant_id=DEFAULT_MERCHANT_ID,
                paytrail_merchant_id="1234567",
            )
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

        merchant_attrs_to_skip = (
            "id",
            "organization",
            "active",
            "paytrail_merchant_id",
        )

        self.assertMerchantValuesNotEqual(
            merchant, data, attrs_to_skip=merchant_attrs_to_skip
        )

        with (
            requests_mock.Mocker() as req_mock,
            self.assertRaises(WebStoreAPIError),
        ):
            req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}merchant/update/"
                f"merchant/{settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

            self.client.post(
                f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
                data,
            )

            self.assertEqual(req_mock.call_count, 1)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        merchant.refresh_from_db()
        self.assertMerchantValuesNotEqual(
            merchant, data, attrs_to_skip=merchant_attrs_to_skip
        )
        self.assertEqual(merchant_last_modified_time, merchant.last_modified_time)

    def test_do_not_update_web_store_merchant_in_talpa_if_data_is_unchanged(self):
        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            merchant = WebStoreMerchantFactory(organization=self.organization)

        merchant_data = self._get_merchant_data(
            update_data={
                "web_store_merchants-INITIAL_FORMS": "1",
                "web_store_merchants-0-id": merchant.pk,
                "web_store_merchants-0-organization": self.organization.pk,
                **{
                    f"web_store_merchants-0-{field}": getattr(merchant, field)
                    for field in WebStoreMerchant._TALPA_SYNCED_FIELDS
                },
            }
        )
        data = self._get_request_data(merchant_data)

        merchant_attrs_to_skip = ("id", "organization", "active")

        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        self.assertMerchantValuesEqual(
            merchant, data, attrs_to_skip=merchant_attrs_to_skip
        )

        with requests_mock.Mocker() as req_mock:
            req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}merchant/update/"
                f"merchant/{settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}",
            )
            req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}merchant/create/"
                f"merchant/{settings.WEB_STORE_API_NAMESPACE}",
            )

            self.client.post(
                f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
                data,
            )

            self.assertEqual(req_mock.call_count, 0)

        merchant.refresh_from_db()
        self.assertMerchantValuesEqual(
            merchant, data, attrs_to_skip=merchant_attrs_to_skip
        )

        self.assertEqual(WebStoreMerchant.objects.count(), 1)

    def test_create_new_web_store_merchant_if_paytrail_merchant_id_changed(self):
        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            # Don't do the full save() with the Talpa API call yet.
            merchant = WebStoreMerchantFactory(organization=self.organization)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        new_merchant_id = "9876"
        new_paytrail_merchant_id = "4321"

        merchant_data = self._get_merchant_data(
            update_data={
                "web_store_merchants-INITIAL_FORMS": "1",
                "web_store_merchants-0-id": merchant.pk,
                "web_store_merchants-0-organization": self.organization.pk,
                "web_store_merchants-0-paytrail_merchant_id": new_paytrail_merchant_id,
            }
        )
        data = self._get_request_data(merchant_data)

        merchant_attrs_to_skip = ("id", "organization", "active")

        self.assertNotEqual(merchant.merchant_id, new_merchant_id)
        self.assertMerchantValuesNotEqual(
            merchant, data, attrs_to_skip=merchant_attrs_to_skip
        )

        json_return_value = deepcopy(DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA)
        json_return_value["merchantId"] = new_merchant_id
        with requests_mock.Mocker() as req_mock:
            req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}merchant/create/"
                f"merchant/{settings.WEB_STORE_API_NAMESPACE}",
                json=json_return_value,
            )

            self.client.post(
                f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
                data,
            )
            self.assertEqual(req_mock.call_count, 1)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreMerchant.objects.count(), 1)

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.web_store_merchants.first().pk, merchant.pk)

        merchant.refresh_from_db()
        self.assertEqual(merchant.merchant_id, new_merchant_id)
        self.assertMerchantValuesEqual(
            merchant, data, attrs_to_skip=merchant_attrs_to_skip
        )


class TestLocalOrganizationAccountAdmin(LocalOrganizationAdminTestCaseMixin, TestCase):
    _ACCOUNT_ATTR_RE = re.compile(r"web_store_accounts-\d+-(\w+)")

    @staticmethod
    def _get_account_data(update_data=None):
        data = {
            "web_store_accounts-TOTAL_FORMS": "1",
            "web_store_accounts-INITIAL_FORMS": "0",
            "web_store_accounts-MIN_NUM_FORMS": "0",
            "web_store_accounts-0-active": "on",
            "web_store_accounts-0-name": "Test Account",
            "web_store_accounts-0-company_code": "4444",
            "web_store_accounts-0-main_ledger_account": "555555",
            "web_store_accounts-0-balance_profit_center": "66666",
        }

        if update_data:
            data.update(update_data)

        return data

    def assertAccountValuesEqual(self, account, data, attrs_to_skip=None):
        attrs_to_skip = attrs_to_skip or []

        for field, value in data.items():
            if match := re.match(self._ACCOUNT_ATTR_RE, field):
                account_attr = match.group(1)
                if account_attr in attrs_to_skip:
                    continue

                if account_attr == "active":
                    account_value = True if value == "on" else False
                    getattr(self, f"assert{account_value}")(account.active)
                else:
                    self.assertEqual(getattr(account, account_attr), value)

    def assertAccountValuesNotEqual(self, account, data, attrs_to_skip=None):
        attrs_to_skip = attrs_to_skip or []

        for field, value in data.items():
            if match := re.match(self._ACCOUNT_ATTR_RE, field):
                account_attr = match.group(1)
                if account_attr in attrs_to_skip:
                    continue

                if account_attr == "active":
                    account_value = False if value == "on" else True
                    getattr(self, f"assert{account_value}")(account.active)
                else:
                    self.assertNotEqual(getattr(account, account_attr), value)

    def test_can_add_web_store_accounts_to_a_new_organization(self):
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreAccount.objects.count(), 0)

        account_data = self._get_account_data()
        account_data2 = {
            "web_store_accounts-TOTAL_FORMS": "2",
            "web_store_accounts-1-active": "on",
            "web_store_accounts-1-name": "Test Account 2",
            "web_store_accounts-1-company_code": "5555",
            "web_store_accounts-1-main_ledger_account": "666666",
            "web_store_accounts-1-balance_profit_center": "77777",
        }
        data = self._get_request_data(
            {
                "name": "New Org",
                "internal_type": "normal",
            }
        )
        data.update(account_data)
        data.update(account_data2)

        response = self.client.post(
            "/admin/django_orghierarchy/organization/add/",
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(WebStoreAccount.objects.count(), 2)

        organization = Organization.objects.last()
        for account_name, account_data in [
            ("Test Account", account_data),
            ("Test Account 2", account_data2),
        ]:
            account = WebStoreAccount.objects.get(
                name=account_name,
                organization_id=organization.pk,
                created_by_id=self.admin_user.pk,
                last_modified_by_id=self.admin_user.pk,
            )
            self.assertIsNotNone(account.created_time)
            self.assertIsNotNone(account.last_modified_time)
            self.assertAccountValuesEqual(account, account_data)

    def test_can_add_web_store_account_to_an_existing_organization(self):
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreAccount.objects.count(), 0)

        account_data = self._get_account_data(
            update_data={"web_store_accounts-0-organization": self.organization.pk}
        )
        data = self._get_request_data(account_data)

        self.client.post(
            f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
            data,
        )

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreAccount.objects.count(), 1)

        account = WebStoreAccount.objects.first()
        self.assertEqual(
            Organization.objects.first().web_store_accounts.first().pk,
            account.pk,
        )
        self.assertEqual(account.created_by_id, self.admin_user.pk)
        self.assertEqual(account.last_modified_by_id, self.admin_user.pk)
        self.assertIsNotNone(account.created_time)
        self.assertIsNotNone(account.last_modified_time)
        self.assertAccountValuesEqual(account, data, attrs_to_skip=["organization"])

    def test_can_edit_web_store_account(self):
        account = WebStoreAccountFactory(organization=self.organization)

        self.assertIsNotNone(account.created_time)
        self.assertIsNotNone(account.last_modified_time)
        account_last_modified_time = account.last_modified_time

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreAccount.objects.count(), 1)

        account_data = self._get_account_data(
            update_data={
                "web_store_accounts-INITIAL_FORMS": "1",
                "web_store_accounts-0-id": account.pk,
                "web_store_accounts-0-organization": self.organization.pk,
            }
        )
        data = self._get_request_data(account_data)

        attrs_to_skip = ("id", "organization", "active")

        self.assertAccountValuesNotEqual(account, data, attrs_to_skip=attrs_to_skip)

        self.client.post(
            f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
            data,
        )

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreAccount.objects.count(), 1)

        self.organization.refresh_from_db()
        account.refresh_from_db()
        self.assertEqual(self.organization.web_store_accounts.first().pk, account.pk)
        self.assertEqual(account.last_modified_by_id, self.admin_user.pk)
        self.assertIsNotNone(account.created_time)
        self.assertIsNotNone(account.last_modified_time)
        self.assertTrue(account.last_modified_time > account_last_modified_time)
        self.assertAccountValuesEqual(account, data, attrs_to_skip=attrs_to_skip)

    def test_can_add_web_store_account_with_all_fields(self):
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreAccount.objects.count(), 0)

        account_data = self._get_account_data(
            update_data={
                "web_store_accounts-0-internal_order": "1234567890",
                "web_store_accounts-0-profit_center": "1234567",
                "web_store_accounts-0-project": "1234567890123456",
                "web_store_accounts-0-operation_area": "123456",
            }
        )
        data = self._get_request_data(
            {
                "name": "New Org",
                "internal_type": "normal",
                **account_data,
            }
        )

        response = self.client.post(
            "/admin/django_orghierarchy/organization/add/",
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(Organization.objects.count(), 2)
        self.assertEqual(WebStoreAccount.objects.count(), 1)

        account = WebStoreAccount.objects.first()
        self.assertEqual(
            Organization.objects.last().web_store_accounts.first().pk,
            account.pk,
        )
        self.assertEqual(account.created_by_id, self.admin_user.pk)
        self.assertEqual(account.last_modified_by_id, self.admin_user.pk)
        self.assertIsNotNone(account.created_time)
        self.assertIsNotNone(account.last_modified_time)
        self.assertAccountValuesEqual(account, data)

    def test_cannot_add_web_store_account_without_all_required_fields(self):
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreAccount.objects.count(), 0)

        for field in [
            "web_store_accounts-0-name",
            "web_store_accounts-0-company_code",
            "web_store_accounts-0-main_ledger_account",
            "web_store_accounts-0-balance_profit_center",
        ]:
            with self.subTest():
                data = self._get_request_data(
                    {
                        "name": "New Org",
                        "internal_type": "normal",
                        **self._get_account_data(),
                    }
                )
                del data[field]

                self.client.post("/admin/django_orghierarchy/organization/add/", data)

                self.assertEqual(Organization.objects.count(), 1)
                self.assertEqual(WebStoreAccount.objects.count(), 0)

    def test_cannot_delete_web_store_account(self):
        account = WebStoreAccountFactory(organization=self.organization)

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreAccount.objects.count(), 1)

        account_data = self._get_account_data(
            update_data={
                "web_store_accounts-INITIAL_FORMS": "1",
                "web_store_accounts-0-name": account.name,
                "web_store_accounts-0-company_code": account.company_code,
                "web_store_accounts-0-main_ledger_account": account.main_ledger_account,
                "web_store_accounts-0-balance_profit_center": account.balance_profit_center,
                "web_store_accounts-0-DELETE": "on",
            }
        )
        data = self._get_request_data(account_data)

        self.client.post(
            f"/admin/django_orghierarchy/organization/{self.organization.id}/change/",
            data,
        )

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(WebStoreAccount.objects.count(), 1)
