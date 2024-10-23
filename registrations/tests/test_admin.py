from decimal import Decimal

import requests_mock
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, TestCase
from django.utils import translation
from requests import RequestException
from rest_framework import status

from events.tests.factories import EventFactory, OfferFactory, OrganizationFactory
from registrations.admin import RegistrationAdmin
from registrations.enums import VatPercentage
from registrations.exceptions import WebStoreAPIError
from registrations.models import (
    VAT_CODE_MAPPING,
    Event,
    PriceGroup,
    Registration,
    RegistrationPriceGroup,
    RegistrationUserAccess,
    RegistrationWebStoreAccount,
    RegistrationWebStoreMerchant,
    RegistrationWebStoreProductMapping,
)
from registrations.tests.factories import (
    PriceGroupFactory,
    RegistrationFactory,
    RegistrationPriceGroupFactory,
    RegistrationWebStoreAccountFactory,
    RegistrationWebStoreMerchantFactory,
    RegistrationWebStoreProductMappingFactory,
    WebStoreAccountFactory,
    WebStoreMerchantFactory,
)
from registrations.tests.utils import assert_invitation_email_is_sent
from registrations.utils import get_signup_create_url
from web_store.tests.product.test_web_store_product_api_client import (
    DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA,
    DEFAULT_GET_PRODUCT_MAPPING_DATA,
    DEFAULT_PRODUCT_ID,
)

EMAIL = "user@email.com"
EDITED_EMAIL = "user_edited@email.com"
EVENT_NAME = "Foo"


def make_admin(username="testadmin", is_superuser=True):
    user_model = get_user_model()
    return user_model.objects.create(
        username=username, is_staff=True, is_superuser=is_superuser
    )


class RegistrationAdminTestCaseMixin:
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.site = AdminSite()

        cls.registration = RegistrationFactory()
        cls.registration_change_url = (
            f"/admin/registrations/registration/{cls.registration.id}/change/"
        )
        cls.registration_add_url = "/admin/registrations/registration/add/"

    def setUp(self):
        self.client.force_login(self.admin)

    @staticmethod
    def _get_request_data(update_data=None):
        data = {
            "registration_user_accesses-TOTAL_FORMS": 1,
            "registration_user_accesses-INITIAL_FORMS": 0,
            "maximum_attendee_capacity": 10000000,
            "minimum_attendee_capacity": 500000,
        }

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            data.update(
                {
                    "registration_price_groups-TOTAL_FORMS": 0,
                    "registration_price_groups-INITIAL_FORMS": 0,
                    "registration_merchant-TOTAL_FORMS": 1,
                    "registration_merchant-INITIAL_FORMS": 0,
                    "registration_merchant-MIN_NUM_FORMS": 0,
                    "registration_merchant-MAX_NUM_FORMS": 1,
                    "registration_account-TOTAL_FORMS": 1,
                    "registration_account-INITIAL_FORMS": 0,
                    "registration_account-MIN_NUM_FORMS": 0,
                    "registration_account-MAX_NUM_FORMS": 1,
                }
            )

        if update_data:
            data.update(update_data)

        return data


class TestRegistrationAdmin(RegistrationAdminTestCaseMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.factory = RequestFactory()

    def test_registrations_admin_is_registered(self):
        is_registered = admin.site.is_registered(Registration)
        self.assertTrue(is_registered)

    def test_readonly_fields(self):
        registration_admin = RegistrationAdmin(Registration, self.site)
        request = self.factory.get("/fake-url/")
        request.user = self.admin

        self.assertEqual(["id"], registration_admin.get_readonly_fields(request))
        self.assertEqual(
            ["id", "event"],
            registration_admin.get_readonly_fields(request, self.registration),
        )

    def test_change_created_by_when_creating_registration(self):
        # Create event for new registration
        data_source = self.registration.event.data_source
        publisher = self.registration.event.publisher
        event2 = Event.objects.create(
            id="event-2", data_source=data_source, publisher=publisher
        )

        # Create new registration
        self.client.post(
            self.registration_add_url,
            self._get_request_data(
                update_data={
                    "event": event2.id,
                    "vat_percentage": VatPercentage.VAT_10.value,
                    "_save": "Save",
                }
            ),
        )

        # Test that create_by values is set to current user
        registration = Registration.objects.get(event=event2)
        self.assertEqual(
            self.admin,
            registration.created_by,
        )

    def test_signup_url_is_linked_to_event_offer_without_info_url(self):
        data_source = self.registration.event.data_source
        publisher = self.registration.event.publisher
        event = EventFactory(id="event-2", data_source=data_source, publisher=publisher)

        for info_url_fi, info_url_sv, info_url_en in [
            (None, None, None),
            (None, None, ""),
            (None, "", ""),
            ("", None, None),
            ("", "", None),
            ("", "", ""),
        ]:
            with self.subTest():
                offer = OfferFactory(
                    event=event,
                    info_url_fi=info_url_fi,
                    info_url_sv=info_url_sv,
                    info_url_en=info_url_en,
                )

                self.assertEqual(Registration.objects.count(), 1)

                self.client.post(
                    self.registration_add_url,
                    self._get_request_data(
                        update_data={
                            "event": event.id,
                            "vat_percentage": VatPercentage.VAT_10.value,
                        }
                    ),
                )

                self.assertEqual(Registration.objects.count(), 2)
                registration = Registration.objects.last()

                offer.refresh_from_db()
                self.assertEqual(
                    offer.info_url_fi, get_signup_create_url(registration, "fi")
                )
                self.assertEqual(
                    offer.info_url_sv, get_signup_create_url(registration, "sv")
                )
                self.assertEqual(
                    offer.info_url_en, get_signup_create_url(registration, "en")
                )

                offer.delete()
                registration.delete()

    def test_signup_url_is_not_linked_to_event_offer_with_info_url_on_update(self):
        blank_values = (None, "")

        for info_url_fi, info_url_sv, info_url_en in [
            (None, None, None),
            (None, None, ""),
            (None, "", ""),
            ("", None, None),
            ("", "", None),
            ("", "", ""),
        ]:
            with self.subTest():
                offer = OfferFactory(
                    event=self.registration.event,
                    info_url_fi=info_url_fi,
                    info_url_sv=info_url_sv,
                    info_url_en=info_url_en,
                )

                response = self.client.post(
                    self.registration_change_url,
                    self._get_request_data(
                        update_data={
                            "event": self.registration.event_id,
                            "vat_percentage": VatPercentage.VAT_10.value,
                        }
                    ),
                )
                assert response.status_code == status.HTTP_302_FOUND
                assert response.url == "/admin/registrations/registration/"

                offer.refresh_from_db()
                self.assertIn(offer.info_url_fi, blank_values)
                self.assertIn(offer.info_url_sv, blank_values)
                self.assertIn(offer.info_url_en, blank_values)

                offer.delete()

    def test_registration_user_accesses_cannot_have_duplicate_emails(self):
        with translation.override("en"):
            # Create event for new registration
            data_source = self.registration.event.data_source
            publisher = self.registration.event.publisher
            event2 = Event.objects.create(
                id="event-2", data_source=data_source, publisher=publisher
            )

            # Create new registration
            response = self.client.post(
                self.registration_add_url,
                self._get_request_data(
                    update_data={
                        "event": event2.id,
                        "vat_percentage": VatPercentage.VAT_10.value,
                        "registration_user_accesses-TOTAL_FORMS": 2,
                        "registration_user_accesses-0-email": EMAIL,
                        "registration_user_accesses-1-email": EMAIL,
                        "_save": "Save",
                    }
                ),
            )

            self.assertContains(
                response, "Please correct the duplicate data for email.", html=True
            )

    def test_send_invitation_email_when_adding_registration_user_access(self):
        with translation.override("fi"):
            # Create event for new registration
            data_source = self.registration.event.data_source
            publisher = self.registration.event.publisher
            event2 = Event.objects.create(
                id="event-2",
                data_source=data_source,
                name=EVENT_NAME,
                publisher=publisher,
            )

            # Create new registration
            response = self.client.post(
                self.registration_add_url,
                self._get_request_data(
                    update_data={
                        "event": event2.id,
                        "vat_percentage": VatPercentage.VAT_10.value,
                        "registration_user_accesses-TOTAL_FORMS": 1,
                        "registration_user_accesses-0-email": EMAIL,
                        "_save": "Save",
                    }
                ),
            )

            assert response.status_code == status.HTTP_302_FOUND
            assert response.url == "/admin/registrations/registration/"

            # Assert that invitation is sent to registration user
            registration_user_access = RegistrationUserAccess.objects.first()
            assert_invitation_email_is_sent(EMAIL, EVENT_NAME, registration_user_access)

    def test_change_last_modified_by_when_updating_registration(self):
        ra = RegistrationAdmin(Registration, self.site)
        request = self.factory.get("/fake-url/")
        request.user = self.admin

        # Update registration
        ra.save_model(
            request,
            self.registration,
            form=ra.get_form(None),
            change=ra.get_action("change"),
        )
        # Test that last_modified_by values is set to current user
        self.assertEqual(
            self.admin,
            self.registration.last_modified_by,
        )

    def test_send_invitation_email_when_registration_user_access_is_updated(self):
        with translation.override("fi"):
            registration_user_access = RegistrationUserAccess.objects.create(
                registration=self.registration, email=EMAIL
            )
            mail.outbox.clear()
            self.registration.event.name = EVENT_NAME
            self.registration.event.save()

            # Update registration
            response = self.client.post(
                self.registration_change_url,
                self._get_request_data(
                    update_data={
                        "event": self.registration.event_id,
                        "vat_percentage": VatPercentage.VAT_10.value,
                        "registration_user_accesses-TOTAL_FORMS": 1,
                        "registration_user_accesses-INITIAL_FORMS": 1,
                        "registration_user_accesses-0-email": EDITED_EMAIL,
                        "registration_user_accesses-0-id": registration_user_access.id,
                        "registration_user_accesses-0-registration": self.registration.id,
                        "_save": "Save",
                    }
                ),
            )

            assert response.status_code == status.HTTP_302_FOUND
            assert response.url == "/admin/registrations/registration/"

            # Assert that invitation is sent to updated email
            registration_user_access.refresh_from_db()
            assert_invitation_email_is_sent(
                EDITED_EMAIL, EVENT_NAME, registration_user_access
            )

    def test_cannot_create_registration_without_maximum_attendee_capacity(self):
        data_source = self.registration.event.data_source
        publisher = self.registration.event.publisher
        event2 = EventFactory(
            id="event-2", data_source=data_source, publisher=publisher
        )

        self.assertEqual(Registration.objects.count(), 1)

        data = self._get_request_data(update_data={"event": event2.id})
        data.pop("maximum_attendee_capacity")

        with translation.override("en"):
            response = self.client.post(self.registration_add_url, data)
        self.assertContains(response, "This field is required.", status_code=200)

        self.assertEqual(Registration.objects.count(), 1)

    def test_cannot_update_registration_without_maximum_attendee_capacity(self):
        self.assertEqual(Registration.objects.count(), 1)
        self.assertIsNone(self.registration.minimum_attendee_capacity)
        self.assertIsNone(self.registration.maximum_attendee_capacity)

        data = self._get_request_data(
            update_data={
                "id": self.registration.id,
                "event": self.registration.event_id,
                "vat_percentage": VatPercentage.VAT_25_5.value,
            }
        )
        data.pop("maximum_attendee_capacity")

        with translation.override("en"):
            response = self.client.post(self.registration_change_url, data)
        self.assertContains(response, "This field is required.", status_code=200)

        self.assertEqual(Registration.objects.count(), 1)

        self.registration.refresh_from_db()
        self.assertIsNone(self.registration.minimum_attendee_capacity)
        self.assertIsNone(self.registration.maximum_attendee_capacity)


class RegistrationPriceGroupTestCase(RegistrationAdminTestCaseMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.price_group = PriceGroupFactory(description="Adults")

    def test_add_new_registration_with_price_groups(self):
        data_source = self.registration.event.data_source
        publisher = self.registration.event.publisher
        event2 = Event.objects.create(
            id="event-2", data_source=data_source, publisher=publisher
        )

        price_group2 = PriceGroupFactory(description="Children")

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

        response = self.client.post(
            self.registration_add_url,
            self._get_request_data(
                update_data={
                    "event": event2.id,
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                    "registration_price_groups-TOTAL_FORMS": 2,
                    "registration_price_groups-0-price_group": self.price_group.pk,
                    "registration_price_groups-0-price": Decimal("10"),
                    "registration_price_groups-1-price_group": price_group2.pk,
                    "registration_price_groups-1-price": Decimal("5"),
                    "_save": "Save",
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(Registration.objects.count(), 2)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 2)
        self.assertEqual(
            RegistrationPriceGroup.objects.exclude(
                registration_id=self.registration.pk
            ).count(),
            2,
        )

        registration_price_group = RegistrationPriceGroup.objects.first()
        self.assertEqual(registration_price_group.price_group_id, self.price_group.pk)
        self.assertEqual(registration_price_group.price, Decimal("10"))
        self.assertEqual(
            registration_price_group.vat_percentage,
            VatPercentage.VAT_25_5.value,
        )
        self.assertEqual(registration_price_group.price_without_vat, Decimal("7.97"))
        self.assertEqual(registration_price_group.vat, Decimal("2.03"))

        registration_price_group2 = RegistrationPriceGroup.objects.last()
        self.assertEqual(registration_price_group2.price_group_id, price_group2.pk)
        self.assertEqual(registration_price_group2.price, Decimal("5"))
        self.assertEqual(
            registration_price_group2.vat_percentage,
            VatPercentage.VAT_25_5.value,
        )
        self.assertEqual(registration_price_group2.price_without_vat, Decimal("3.98"))
        self.assertEqual(registration_price_group2.vat, Decimal("1.02"))

    def test_add_price_groups_to_existing_registration(self):
        price_group2 = PriceGroupFactory(description="Children")

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

        response = self.client.post(
            self.registration_change_url,
            self._get_request_data(
                update_data={
                    "event": self.registration.event.id,
                    "vat_percentage": VatPercentage.VAT_14.value,
                    "registration_price_groups-TOTAL_FORMS": 2,
                    "registration_price_groups-0-registration": self.registration.id,
                    "registration_price_groups-0-price_group": self.price_group.pk,
                    "registration_price_groups-0-price": Decimal("10"),
                    "registration_price_groups-1-registration": self.registration.id,
                    "registration_price_groups-1-price_group": price_group2.pk,
                    "registration_price_groups-1-price": Decimal("5"),
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 2)
        self.assertEqual(
            RegistrationPriceGroup.objects.filter(
                registration_id=self.registration.pk
            ).count(),
            2,
        )

        registration_price_group = RegistrationPriceGroup.objects.first()
        self.assertEqual(registration_price_group.price_group_id, self.price_group.pk)
        self.assertEqual(registration_price_group.price, Decimal("10"))
        self.assertEqual(
            registration_price_group.vat_percentage,
            VatPercentage.VAT_14.value,
        )
        self.assertEqual(registration_price_group.price_without_vat, Decimal("8.77"))
        self.assertEqual(registration_price_group.vat, Decimal("1.23"))

        registration_price_group2 = RegistrationPriceGroup.objects.last()
        self.assertEqual(registration_price_group2.price_group_id, price_group2.pk)
        self.assertEqual(registration_price_group2.price, Decimal("5"))
        self.assertEqual(
            registration_price_group2.vat_percentage,
            VatPercentage.VAT_14.value,
        )
        self.assertEqual(registration_price_group2.price_without_vat, Decimal("4.39"))
        self.assertEqual(registration_price_group2.vat, Decimal("0.61"))

    def test_cannot_add_duplicate_price_groups_to_registration(self):
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

        response = self.client.post(
            self.registration_change_url,
            self._get_request_data(
                update_data={
                    "event": self.registration.event.id,
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                    "registration_price_groups-TOTAL_FORMS": 2,
                    "registration_price_groups-0-registration": self.registration.id,
                    "registration_price_groups-0-price_group": self.price_group.pk,
                    "registration_price_groups-0-price": Decimal("10"),
                    "registration_price_groups-1-registration": self.registration.id,
                    "registration_price_groups-1-price_group": self.price_group.pk,
                    "registration_price_groups-1-price": Decimal("5"),
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

    def test_cannot_use_more_than_two_decimals_for_registration_price_group_price(self):
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

        response = self.client.post(
            self.registration_change_url,
            self._get_request_data(
                update_data={
                    "event": self.registration.event_id,
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                    "registration_price_groups-TOTAL_FORMS": 2,
                    "registration_price_groups-0-registration": self.registration.id,
                    "registration_price_groups-0-price_group": self.price_group.pk,
                    "registration_price_groups-0-price": Decimal("10.123"),
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

    def test_delete_price_group_from_registration(self):
        registration_price_group = RegistrationPriceGroupFactory(
            registration=self.registration,
            price_group=self.price_group,
            price=Decimal("10"),
        )
        RegistrationWebStoreProductMappingFactory(registration=self.registration)

        self.assertEqual(RegistrationPriceGroup.objects.count(), 1)

        response = self.client.post(
            self.registration_change_url,
            self._get_request_data(
                update_data={
                    "event": self.registration.event_id,
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                    "registration_price_groups-TOTAL_FORMS": 1,
                    "registration_price_groups-INITIAL_FORMS": 1,
                    "registration_price_groups-0-id": registration_price_group.id,
                    "registration_price_groups-0-registration": self.registration.id,
                    "registration_price_groups-0-price_group": registration_price_group.price_group_id,
                    "registration_price_groups-0-price": registration_price_group.price,
                    "registration_price_groups-0-DELETE": "on",
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

    def test_vat_percentages(self):
        data_source = self.registration.event.data_source
        publisher = self.registration.event.publisher
        event2 = Event.objects.create(
            id="event-2", data_source=data_source, publisher=publisher
        )

        price_with_vat = Decimal("10")
        data = self._get_request_data(
            update_data={
                "event": event2.id,
                "registration_price_groups-TOTAL_FORMS": 1,
                "registration_price_groups-0-price_group": self.price_group.pk,
                "registration_price_groups-0-price": price_with_vat,
            }
        )

        expected_values = [
            (VatPercentage.VAT_0.value, Decimal("10"), Decimal("0")),
            (
                VatPercentage.VAT_10.value,
                Decimal("9.09"),
                Decimal("0.91"),
            ),
            (
                VatPercentage.VAT_14.value,
                Decimal("8.77"),
                Decimal("1.23"),
            ),
            (
                VatPercentage.VAT_25_5.value,
                Decimal("7.97"),
                Decimal("2.03"),
            ),
        ]
        for vat_percentage, price_without_vat, vat_amount in expected_values:
            with self.subTest():
                self.assertEqual(Registration.objects.count(), 1)
                self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

                data["vat_percentage"] = vat_percentage
                response = self.client.post(
                    self.registration_add_url,
                    data,
                )
                self.assertEqual(response.status_code, status.HTTP_302_FOUND)

                self.assertEqual(Registration.objects.count(), 2)
                self.assertEqual(RegistrationPriceGroup.objects.count(), 1)

                registration_price_group = RegistrationPriceGroup.objects.first()
                self.assertEqual(
                    registration_price_group.vat_percentage,
                    vat_percentage,
                )
                self.assertEqual(registration_price_group.price, price_with_vat)
                self.assertEqual(
                    registration_price_group.price_without_vat, price_without_vat
                )
                self.assertEqual(registration_price_group.vat, vat_amount)

                Registration.objects.last().delete()
                RegistrationPriceGroup.objects.all().delete()


class RegistrationWebStoreProductMappingBaseTestCase(RegistrationAdminTestCaseMixin):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.publisher = cls.registration.event.publisher

        cls.web_store_product_url = f"{settings.WEB_STORE_API_BASE_URL}product/"
        cls.web_store_accounting_url = (
            f"{cls.web_store_product_url}{DEFAULT_PRODUCT_ID}/accounting"
        )


class RegistrationWebStoreProductMappingTestCase(
    RegistrationWebStoreProductMappingBaseTestCase, TestCase
):
    def test_create_product_mapping_for_new_registration(self):
        data_source = self.registration.event.data_source
        event2 = Event.objects.create(
            id="event-2", data_source=data_source, publisher=self.publisher
        )

        price_group = PriceGroupFactory(description="Adults")
        price_group2 = PriceGroupFactory(description="Children")

        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            merchant = WebStoreMerchantFactory(
                organization=self.publisher, merchant_id="1234"
            )
        account = WebStoreAccountFactory(organization=self.publisher)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

        with requests_mock.Mocker() as req_mock:
            req_mock.post(
                self.web_store_product_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA
            )
            req_mock.post(
                self.web_store_accounting_url,
                json=DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA,
            )

            response = self.client.post(
                self.registration_add_url,
                self._get_request_data(
                    update_data={
                        "event": event2.id,
                        "vat_percentage": VatPercentage.VAT_25_5.value,
                        "registration_price_groups-TOTAL_FORMS": 2,
                        "registration_price_groups-0-price_group": price_group.pk,
                        "registration_price_groups-0-price": Decimal("10"),
                        "registration_price_groups-1-price_group": price_group2.pk,
                        "registration_price_groups-1-price": Decimal("5"),
                        "registration_merchant-TOTAL_FORMS": 1,
                        "registration_merchant-0-merchant": merchant.pk,
                        "registration_merchant-0-external_merchant_id": merchant.merchant_id,
                        "registration_account-TOTAL_FORMS": 1,
                        "registration_account-0-account": account.pk,
                        "registration_account-0-name": account.name,
                        "registration_account-0-company_code": account.company_code,
                        "registration_account-0-main_ledger_account": account.main_ledger_account,
                        "registration_account-0-balance_profit_center": account.balance_profit_center,
                        "_save": "Save",
                    }
                ),
            )
            self.assertEqual(response.status_code, status.HTTP_302_FOUND)

            self.assertEqual(req_mock.call_count, 2)

        self.assertEqual(Registration.objects.count(), 2)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 2)

        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 1)

        new_registration = Registration.objects.last()
        self.assertEqual(
            RegistrationWebStoreProductMapping.objects.filter(
                registration=new_registration,
                external_product_id=DEFAULT_PRODUCT_ID,
            ).count(),
            1,
        )
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 1)
        self.assertEqual(
            RegistrationWebStoreMerchant.objects.filter(
                registration=new_registration,
                merchant=merchant,
                external_merchant_id=merchant.merchant_id,
            ).count(),
            1,
        )
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 1)
        self.assertEqual(
            RegistrationWebStoreAccount.objects.filter(
                registration=new_registration,
                account=account,
            ).count(),
            1,
        )

    def test_create_product_mapping_for_existing_registration(self):
        price_group = PriceGroupFactory(description="Adults")
        price_group2 = PriceGroupFactory(description="Children")

        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            registration_merchant = RegistrationWebStoreMerchantFactory(
                registration=self.registration,
            )
        registration_account = RegistrationWebStoreAccountFactory(
            registration=self.registration
        )

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 1)

        with requests_mock.Mocker() as req_mock:
            req_mock.post(
                self.web_store_product_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA
            )
            req_mock.post(
                self.web_store_accounting_url,
                json=DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA,
            )

            response = self.client.post(
                self.registration_change_url,
                self._get_request_data(
                    update_data={
                        "event": self.registration.event_id,
                        "vat_percentage": VatPercentage.VAT_14.value,
                        "registration_price_groups-TOTAL_FORMS": 2,
                        "registration_price_groups-0-registration": self.registration.id,
                        "registration_price_groups-0-price_group": price_group.pk,
                        "registration_price_groups-0-price": Decimal("10"),
                        "registration_price_groups-1-registration": self.registration.id,
                        "registration_price_groups-1-price_group": price_group2.pk,
                        "registration_price_groups-1-price": Decimal("5"),
                        "registration_merchant-TOTAL_FORMS": 1,
                        "registration_merchant-INITIAL_FORMS": 1,
                        "registration_merchant-0-registration": registration_merchant.pk,
                        "registration_merchant-0-merchant": registration_merchant.merchant_id,
                        "registration_merchant-0-external_merchant_id": registration_merchant.merchant_id,
                        "registration_account-TOTAL_FORMS": 1,
                        "registration_account-INITIAL_FORMS": 1,
                        "registration_account-0-registration": registration_account.pk,
                        "registration_account-0-account": registration_account.account_id,
                        "registration_account-0-name": registration_account.name,
                        "registration_account-0-company_code": registration_account.company_code,
                        "registration_account-0-main_ledger_account": registration_account.main_ledger_account,
                        "registration_account-0-balance_profit_center": registration_account.balance_profit_center,
                    }
                ),
            )
            self.assertEqual(response.status_code, status.HTTP_302_FOUND)

            self.assertEqual(req_mock.call_count, 2)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 2)

        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 1)
        self.assertEqual(
            RegistrationWebStoreProductMapping.objects.filter(
                registration=self.registration,
                external_product_id=DEFAULT_PRODUCT_ID,
            ).count(),
            1,
        )
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 1)
        self.assertEqual(
            RegistrationWebStoreMerchant.objects.filter(
                registration=self.registration,
                merchant=registration_merchant.merchant,
                external_merchant_id=registration_merchant.merchant.merchant_id,
            ).count(),
            1,
        )
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 1)
        self.assertEqual(
            RegistrationWebStoreAccount.objects.filter(
                registration=self.registration,
                account=registration_account.account,
            ).count(),
            1,
        )

    def test_update_product_mapping_if_vat_code_changed(self):
        registration_price_group = RegistrationPriceGroupFactory(
            registration=self.registration
        )

        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            registration_merchant = RegistrationWebStoreMerchantFactory(
                registration=self.registration,
            )
        registration_account = RegistrationWebStoreAccountFactory(
            registration=self.registration
        )
        product_mapping = RegistrationWebStoreProductMappingFactory(
            registration=self.registration, external_product_id="4321"
        )

        self.assertEqual(RegistrationPriceGroup.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 1)

        self.assertNotEqual(product_mapping.external_product_id, DEFAULT_PRODUCT_ID)
        self.assertNotEqual(
            product_mapping.vat_code, VAT_CODE_MAPPING[VatPercentage.VAT_10.value]
        )

        with requests_mock.Mocker() as req_mock:
            req_mock.post(
                self.web_store_product_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA
            )
            req_mock.post(
                self.web_store_accounting_url,
                json=DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA,
            )

            response = self.client.post(
                self.registration_change_url,
                self._get_request_data(
                    update_data={
                        "event": self.registration.event_id,
                        "vat_percentage": VatPercentage.VAT_10.value,
                        "registration_price_groups-TOTAL_FORMS": 1,
                        "registration_price_groups-INITIAL_FORMS": 1,
                        "registration_price_groups-0-id": registration_price_group.id,
                        "registration_price_groups-0-registration": self.registration.id,
                        "registration_price_groups-0-price_group": registration_price_group.price_group_id,
                        "registration_price_groups-0-price": registration_price_group.price,
                        "registration_merchant-TOTAL_FORMS": 1,
                        "registration_merchant-INITIAL_FORMS": 1,
                        "registration_merchant-0-registration": registration_merchant.pk,
                        "registration_merchant-0-merchant": registration_merchant.merchant_id,
                        "registration_merchant-0-external_merchant_id": registration_merchant.merchant_id,
                        "registration_account-TOTAL_FORMS": 1,
                        "registration_account-INITIAL_FORMS": 1,
                        "registration_account-0-registration": registration_account.pk,
                        "registration_account-0-account": registration_account.account_id,
                        "registration_account-0-name": registration_account.name,
                        "registration_account-0-company_code": registration_account.company_code,
                        "registration_account-0-main_ledger_account": registration_account.main_ledger_account,
                        "registration_account-0-balance_profit_center": registration_account.balance_profit_center,
                    }
                ),
            )
            self.assertEqual(response.status_code, status.HTTP_302_FOUND)

            self.assertEqual(req_mock.call_count, 2)

        self.assertEqual(RegistrationPriceGroup.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 1)

        product_mapping.refresh_from_db()
        self.assertEqual(product_mapping.external_product_id, DEFAULT_PRODUCT_ID)
        self.assertEqual(
            product_mapping.vat_code, VAT_CODE_MAPPING[VatPercentage.VAT_10.value]
        )

    def test_dont_create_product_mapping_for_new_registration_if_merchant_missing(self):
        data_source = self.registration.event.data_source
        event2 = EventFactory(
            id="event-2", data_source=data_source, publisher=self.publisher
        )

        price_group = PriceGroup.objects.first()

        account = WebStoreAccountFactory(organization=self.publisher)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

        self.client.post(
            self.registration_add_url,
            self._get_request_data(
                update_data={
                    "event": event2.id,
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                    "registration_user_accesses-TOTAL_FORMS": 1,
                    "registration_price_groups-TOTAL_FORMS": 1,
                    "registration_price_groups-0-price_group": price_group.pk,
                    "registration_price_groups-0-price": Decimal("10"),
                    "registration_account-TOTAL_FORMS": 1,
                    "registration_account-0-account": account.pk,
                    "registration_account-0-name": account.name,
                    "registration_account-0-company_code": account.company_code,
                    "registration_account-0-main_ledger_account": account.main_ledger_account,
                    "registration_account-0-balance_profit_center": account.balance_profit_center,
                    "_save": "Save",
                }
            ),
        )

        self.assertEqual(Registration.objects.count(), 2)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 1)

    def test_dont_create_product_mapping_for_new_registration_if_account_missing(self):
        data_source = self.registration.event.data_source
        event2 = EventFactory(
            id="event-2", data_source=data_source, publisher=self.publisher
        )

        price_group = PriceGroup.objects.first()

        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            merchant = WebStoreMerchantFactory(
                organization=self.publisher, merchant_id="1234"
            )

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

        self.client.post(
            self.registration_add_url,
            self._get_request_data(
                update_data={
                    "event": event2.id,
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                    "registration_price_groups-TOTAL_FORMS": 1,
                    "registration_price_groups-0-price_group": price_group.pk,
                    "registration_price_groups-0-price": Decimal("10"),
                    "registration_merchant-TOTAL_FORMS": 1,
                    "registration_merchant-0-merchant": merchant.pk,
                    "registration_merchant-0-external_merchant_id": merchant.merchant_id,
                    "_save": "Save",
                }
            ),
        )

        self.assertEqual(Registration.objects.count(), 2)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

    def test_dont_create_product_mapping_for_new_registration_if_merchant_and_account_missing(
        self,
    ):
        data_source = self.registration.event.data_source
        event2 = EventFactory(
            id="event-2", data_source=data_source, publisher=self.publisher
        )

        price_group = PriceGroup.objects.first()

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

        self.client.post(
            self.registration_add_url,
            self._get_request_data(
                update_data={
                    "event": event2.id,
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                    "registration_user_accesses-TOTAL_FORMS": 1,
                    "registration_price_groups-TOTAL_FORMS": 1,
                    "registration_price_groups-0-price_group": price_group.pk,
                    "registration_price_groups-0-price": Decimal("10"),
                    "_save": "Save",
                }
            ),
        )

        self.assertEqual(Registration.objects.count(), 2)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

    def test_web_store_product_mapping_and_accounting_api_exception_when_creating_registration(
        self,
    ):
        data_source = self.registration.event.data_source
        event2 = EventFactory(
            id="event-2", data_source=data_source, publisher=self.publisher
        )

        price_group = PriceGroup.objects.first()

        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            merchant = WebStoreMerchantFactory(
                organization=self.publisher, merchant_id="1234"
            )
        account = WebStoreAccountFactory(organization=self.publisher)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

        with requests_mock.Mocker() as req_mock, self.assertRaises(WebStoreAPIError):
            req_mock.post(
                self.web_store_product_url,
                json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
            )
            req_mock.post(
                self.web_store_accounting_url,
                exc=RequestException,
            )

            self.client.post(
                self.registration_add_url,
                self._get_request_data(
                    update_data={
                        "event": event2.id,
                        "vat_percentage": VatPercentage.VAT_25_5.value,
                        "registration_price_groups-TOTAL_FORMS": 1,
                        "registration_price_groups-0-price_group": price_group.pk,
                        "registration_price_groups-0-price": Decimal("10"),
                        "registration_merchant-TOTAL_FORMS": 1,
                        "registration_merchant-0-merchant": merchant.pk,
                        "registration_merchant-0-external_merchant_id": merchant.merchant_id,
                        "registration_account-TOTAL_FORMS": 1,
                        "registration_account-0-account": account.pk,
                        "registration_account-0-name": account.name,
                        "registration_account-0-company_code": account.company_code,
                        "registration_account-0-main_ledger_account": account.main_ledger_account,
                        "registration_account-0-balance_profit_center": account.balance_profit_center,
                        "_save": "Save",
                    }
                ),
            )

            self.assertEqual(req_mock.call_count, 1)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

    def test_web_store_product_mapping_accounting_api_exception_when_updating_registration(
        self,
    ):
        registration_price_group = RegistrationPriceGroupFactory(
            registration=self.registration
        )

        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            merchant = WebStoreMerchantFactory(
                organization=self.publisher, merchant_id="1234"
            )
        account = WebStoreAccountFactory(organization=self.publisher)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

        with requests_mock.Mocker() as req_mock, self.assertRaises(WebStoreAPIError):
            req_mock.post(
                self.web_store_product_url,
                json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
            )
            req_mock.post(
                self.web_store_accounting_url,
                exc=RequestException,
            )

            self.client.post(
                self.registration_change_url,
                self._get_request_data(
                    update_data={
                        "event": self.registration.event_id,
                        "vat_percentage": VatPercentage.VAT_25_5.value,
                        "registration_price_groups-INITIAL_FORMS": 1,
                        "registration_price_groups-TOTAL_FORMS": 1,
                        "registration_price_groups-0-id": registration_price_group.pk,
                        "registration_price_groups-0-price_group": registration_price_group.price_group_id,
                        "registration_price_groups-0-price": registration_price_group.price,
                        "registration_merchant-TOTAL_FORMS": 1,
                        "registration_merchant-0-merchant": merchant.pk,
                        "registration_merchant-0-external_merchant_id": merchant.merchant_id,
                        "registration_account-TOTAL_FORMS": 1,
                        "registration_account-0-account": account.pk,
                        "registration_account-0-name": account.name,
                        "registration_account-0-company_code": account.company_code,
                        "registration_account-0-main_ledger_account": account.main_ledger_account,
                        "registration_account-0-balance_profit_center": account.balance_profit_center,
                    }
                ),
            )

            self.assertEqual(req_mock.call_count, 1)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 0)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)


class RegistrationWebStoreMerchantTestCase(
    RegistrationWebStoreProductMappingBaseTestCase, TestCase
):
    def test_update_product_mapping_if_merchant_changed(self):
        registration_price_group = RegistrationPriceGroupFactory(
            registration=self.registration
        )

        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            registration_merchant = RegistrationWebStoreMerchantFactory(
                registration=self.registration
            )
            new_merchant = WebStoreMerchantFactory(
                organization=self.publisher, merchant_id="1234"
            )

        registration_account = RegistrationWebStoreAccountFactory(
            registration=self.registration
        )

        product_mapping = RegistrationWebStoreProductMappingFactory(
            registration=self.registration
        )
        self.assertEqual(product_mapping.external_product_id, DEFAULT_PRODUCT_ID)

        self.assertNotEqual(registration_merchant.merchant_id, new_merchant.merchant_id)

        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 1)

        new_product_id = "4321"
        product_mapping_json = DEFAULT_GET_PRODUCT_MAPPING_DATA.copy()
        product_mapping_json["productId"] = new_product_id

        with requests_mock.Mocker() as req_mock:
            req_mock.post(self.web_store_product_url, json=product_mapping_json)
            req_mock.post(
                f"{self.web_store_product_url}{new_product_id}/accounting",
                json=DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA,
            )

            response = self.client.post(
                self.registration_change_url,
                self._get_request_data(
                    update_data={
                        "event": self.registration.event_id,
                        "vat_percentage": VatPercentage.VAT_25_5.value,
                        "registration_price_groups-INITIAL_FORMS": 1,
                        "registration_price_groups-TOTAL_FORMS": 1,
                        "registration_price_groups-0-id": registration_price_group.pk,
                        "registration_price_groups-0-price_group": registration_price_group.price_group_id,
                        "registration_price_groups-0-price": registration_price_group.price,
                        "registration_merchant-INITIAL_FORMS": 1,
                        "registration_merchant-TOTAL_FORMS": 1,
                        "registration_merchant-0-registration": self.registration.pk,
                        "registration_merchant-0-merchant": new_merchant.pk,
                        "registration_merchant-0-external_merchant_id": new_merchant.merchant_id,
                        "registration_account-INITIAL_FORMS": 1,
                        "registration_account-TOTAL_FORMS": 1,
                        "registration_account-0-registration": self.registration.pk,
                        "registration_account-0-account": registration_account.account_id,
                        "registration_account-0-name": registration_account.name,
                        "registration_account-0-company_code": registration_account.company_code,
                        "registration_account-0-main_ledger_account": registration_account.main_ledger_account,
                        "registration_account-0-balance_profit_center": registration_account.balance_profit_center,
                    }
                ),
            )
            self.assertEqual(response.status_code, status.HTTP_302_FOUND)

            self.assertEqual(req_mock.call_count, 2)

        registration_merchant.refresh_from_db()
        self.assertEqual(registration_merchant.merchant_id, new_merchant.pk)
        self.assertEqual(
            registration_merchant.external_merchant_id, new_merchant.merchant_id
        )

        product_mapping.refresh_from_db()
        self.assertEqual(product_mapping.external_product_id, new_product_id)


class RegistrationWebStoreAccountTestCase(
    RegistrationWebStoreProductMappingBaseTestCase, TestCase
):
    def test_cannot_add_account_without_account_selection(self):
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

        all_account_fields = (
            "name",
            "company_code",
            "main_ledger_account",
            "balance_profit_center",
            "profit_center",
            "operation_area",
            "internal_order",
            "project",
        )
        account = WebStoreAccountFactory(
            organization=self.publisher,
            name="Account",
            company_code="4321",
            main_ledger_account="123400",
            balance_profit_center="0234567890",
            internal_order="1010101010",
            profit_center="7777777",
            project="1234567890666666",
            operation_area="666666",
        )

        response = self.client.post(
            self.registration_change_url,
            self._get_request_data(
                update_data={
                    "event": self.registration.event_id,
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                    "registration_account-INITIAL_FORMS": 0,
                    "registration_account-TOTAL_FORMS": 1,
                    **{
                        f"registration_account-0-{field}": getattr(account, field, "")
                        for field in all_account_fields
                    },
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

    def test_add_new_account_with_account_values(self):
        all_account_fields = (
            "name",
            "company_code",
            "main_ledger_account",
            "balance_profit_center",
            "profit_center",
            "operation_area",
            "internal_order",
            "project",
        )
        account = WebStoreAccountFactory(
            organization=self.publisher,
            name="Account",
            company_code="4321",
            main_ledger_account="123400",
            balance_profit_center="0234567890",
            internal_order="1010101010",
            profit_center="7777777",
            project="1234567890666666",
            operation_area="666666",
        )

        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

        response = self.client.post(
            self.registration_change_url,
            self._get_request_data(
                update_data={
                    "event": self.registration.event_id,
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                    "registration_account-INITIAL_FORMS": 0,
                    "registration_account-TOTAL_FORMS": 1,
                    "registration_account-0-account": account.pk,
                    **{
                        f"registration_account-0-{field}": getattr(account, field, "")
                        for field in all_account_fields
                    },
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 1)

        registration_account = RegistrationWebStoreAccount.objects.first()
        for field in all_account_fields:
            self.assertEqual(
                getattr(registration_account, field),
                getattr(account, field),
            )

    def test_add_new_account_with_value_overrides(self):
        new_account = WebStoreAccountFactory(
            organization=self.publisher,
            name="Account",
            company_code="4321",
            main_ledger_account="123400",
            balance_profit_center="0234567890",
            internal_order="1010101010",
            profit_center="7777777",
            project="1234567890666666",
            operation_area="666666",
        )
        new_value = "45"

        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 0)

        response = self.client.post(
            self.registration_change_url,
            self._get_request_data(
                update_data={
                    "event": self.registration.event_id,
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                    "registration_account-INITIAL_FORMS": 0,
                    "registration_account-TOTAL_FORMS": 1,
                    "registration_account-0-account": new_account.pk,
                    "registration_account-0-name": new_value,
                    "registration_account-0-company_code": new_value,
                    "registration_account-0-main_ledger_account": new_value,
                    "registration_account-0-balance_profit_center": new_value,
                    "registration_account-0-internal_order": "",
                    "registration_account-0-profit_center": new_value,
                    "registration_account-0-project": "",
                    "registration_account-0-operation_area": new_value,
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 1)

        registration_account = RegistrationWebStoreAccount.objects.first()
        for field in (
            "name",
            "company_code",
            "main_ledger_account",
            "balance_profit_center",
            "profit_center",
            "operation_area",
        ):
            self.assertEqual(
                getattr(registration_account, field),
                new_value,
            )
        for field in ("internal_order", "project"):
            self.assertEqual(
                getattr(registration_account, field),
                "",
            )

    def test_update_account_with_value_overrides(self):
        registration_account = RegistrationWebStoreAccountFactory(
            registration=self.registration,
            internal_order="1010101010",
            project="1234567890666666",
        )

        new_account = WebStoreAccountFactory(
            organization=self.publisher,
            name="Account",
            company_code="4321",
            main_ledger_account="123400",
            balance_profit_center="0234567890",
            internal_order="1010101010",
            profit_center="7777777",
            project="1234567890666666",
            operation_area="666666",
        )
        new_value = "45"

        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 1)

        fields_with_value = (
            "name",
            "company_code",
            "main_ledger_account",
            "balance_profit_center",
            "profit_center",
            "operation_area",
        )
        for field in fields_with_value:
            self.assertNotEqual(
                getattr(registration_account, field),
                getattr(new_account, field),
            )

        fields_without_value = ("internal_order", "project")
        for field in fields_without_value:
            self.assertNotEqual(
                getattr(registration_account, field),
                "",
            )

        response = self.client.post(
            self.registration_change_url,
            self._get_request_data(
                update_data={
                    "event": self.registration.event_id,
                    "vat_percentage": VatPercentage.VAT_25_5.value,
                    "registration_account-INITIAL_FORMS": 1,
                    "registration_account-TOTAL_FORMS": 1,
                    "registration_account-0-registration": self.registration.pk,
                    "registration_account-0-account": new_account.pk,
                    "registration_account-0-name": new_value,
                    "registration_account-0-company_code": new_value,
                    "registration_account-0-main_ledger_account": new_value,
                    "registration_account-0-balance_profit_center": new_value,
                    "registration_account-0-internal_order": "",
                    "registration_account-0-profit_center": new_value,
                    "registration_account-0-project": "",
                    "registration_account-0-operation_area": new_value,
                }
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 1)

        registration_account.refresh_from_db()
        for field in fields_with_value:
            self.assertEqual(
                getattr(registration_account, field),
                new_value,
            )
        for field in fields_without_value:
            self.assertEqual(
                getattr(registration_account, field),
                "",
            )

    def test_update_product_mapping_if_account_changed(self):
        registration_price_group = RegistrationPriceGroupFactory(
            registration=self.registration
        )

        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            RegistrationWebStoreMerchantFactory(registration=self.registration)

        registration_account = RegistrationWebStoreAccountFactory(
            registration=self.registration
        )
        new_account = WebStoreAccountFactory(organization=self.publisher)

        product_mapping = RegistrationWebStoreProductMappingFactory(
            registration=self.registration
        )

        self.assertEqual(product_mapping.external_product_id, DEFAULT_PRODUCT_ID)

        self.assertNotEqual(registration_account.account_id, new_account.pk)

        self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreMerchant.objects.count(), 1)
        self.assertEqual(RegistrationWebStoreAccount.objects.count(), 1)

        new_product_id = "4321"
        product_mapping_json = DEFAULT_GET_PRODUCT_MAPPING_DATA.copy()
        product_mapping_json["productId"] = new_product_id

        with requests_mock.Mocker() as req_mock:
            req_mock.post(self.web_store_product_url, json=product_mapping_json)
            req_mock.post(
                f"{self.web_store_product_url}{new_product_id}/accounting",
                json=DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA,
            )

            response = self.client.post(
                self.registration_change_url,
                self._get_request_data(
                    update_data={
                        "event": self.registration.event_id,
                        "vat_percentage": VatPercentage.VAT_25_5.value,
                        "registration_price_groups-INITIAL_FORMS": 1,
                        "registration_price_groups-TOTAL_FORMS": 1,
                        "registration_price_groups-0-id": registration_price_group.pk,
                        "registration_price_groups-0-price_group": registration_price_group.price_group_id,
                        "registration_price_groups-0-price": registration_price_group.price,
                        "registration_account-INITIAL_FORMS": 1,
                        "registration_account-TOTAL_FORMS": 1,
                        "registration_account-0-registration": self.registration.pk,
                        "registration_account-0-account": new_account.pk,
                        "registration_account-0-name": new_account.name,
                        "registration_account-0-company_code": new_account.company_code,
                        "registration_account-0-main_ledger_account": new_account.main_ledger_account,
                        "registration_account-0-balance_profit_center": new_account.balance_profit_center,
                    }
                ),
            )
            self.assertEqual(response.status_code, status.HTTP_302_FOUND)

            self.assertEqual(req_mock.call_count, 2)

        registration_account.refresh_from_db()
        self.assertEqual(registration_account.account_id, new_account.pk)

        product_mapping.refresh_from_db()
        self.assertEqual(product_mapping.external_product_id, new_product_id)


class TestPriceGroupAdmin(TestCase):
    _DEFAULT_GROUP_DESCRIPTIONS = [
        "Adult",
        "Child (7-17 years)",
        "Child (under 7 years)",
        "Student",
        "Pensioner",
        "War veteran or member of Lotta Svärd",
        "Conscript or subject to civil service",
        "Unemployed",
    ]

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.site = AdminSite()
        cls.base_url = "/admin/registrations/pricegroup/"
        cls.publisher = OrganizationFactory(name="Test Organization 1")

    def _create_custom_price_groups(self):
        self.price_group1 = PriceGroupFactory(
            publisher=self.publisher,
            description="Adults",
        )
        self.price_group2 = PriceGroupFactory(
            publisher=self.publisher,
            description="Students",
        )
        self.price_group3 = PriceGroupFactory(
            publisher=OrganizationFactory(name="Test Organization 2"),
            description="Children",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_price_group_admin_is_registered(self):
        is_registered = admin.site.is_registered(PriceGroup)
        self.assertTrue(is_registered)

    def test_default_price_groups(self):
        self.assertEqual(PriceGroup.objects.count(), 8)
        self.assertEqual(PriceGroup.objects.filter(publisher=None).count(), 8)

        with translation.override("en"):
            response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for description in self._DEFAULT_GROUP_DESCRIPTIONS:
            self.assertContains(response, description)

        with translation.override("fi"):
            response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for description in [
            "Aikuinen",
            "Lapsi (7-17 vuotta)",
            "Lapsi (alle 7 vuotta)",
            "Opiskelija",
            "Eläkeläinen",
            "Sotaveteraani tai lotta",
            "Ase- tai siviilipalvelusvelvollinen",
            "Työtön",
        ]:
            self.assertContains(response, description)

        with translation.override("sv"):
            response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for description in [
            "Vuxen",
            "Barn (7-17 år)",
            "Barn (under 7 år)",
            "Studerande",
            "Pensionär",
            "Krigsveteranen eller medlem av Lotta Svärd",
            "Beväring eller civiltjänstgörare",
            "Arbetslös",
        ]:
            self.assertContains(response, description)

    def test_list_price_groups_with_custom_price_groups(self):
        self._create_custom_price_groups()

        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertContains(response, self.price_group1.publisher.name)
        self.assertContains(response, self.price_group1.description)

        self.assertContains(response, self.price_group2.publisher.name)
        self.assertContains(response, self.price_group2.description)

        self.assertContains(response, self.price_group3.publisher.name)
        self.assertContains(response, self.price_group3.description)

    def test_filter_list_by_description(self):
        self._create_custom_price_groups()

        response1 = self.client.get(
            f"{self.base_url}?q={self.price_group1.description}"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertContains(response1, self.price_group1.description)
        self.assertNotContains(response1, self.price_group2.description)
        self.assertNotContains(response1, self.price_group3.description)

        response2 = self.client.get(
            f"{self.base_url}?q={self.price_group2.description}"
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertNotContains(response2, self.price_group1.description)
        self.assertContains(response2, self.price_group2.description)
        self.assertNotContains(response2, self.price_group3.description)

        response3 = self.client.get(
            f"{self.base_url}?q={self.price_group3.description}"
        )
        self.assertEqual(response3.status_code, status.HTTP_200_OK)
        self.assertNotContains(response3, self.price_group1.description)
        self.assertNotContains(response3, self.price_group2.description)
        self.assertContains(response3, self.price_group3.description)

    def filter_list_by_publisher(self):
        self._create_custom_price_groups()

        response1 = self.client.get(
            f"{self.base_url}?publisher__pk__exact={self.publisher.pk}"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertContains(response1, self.price_group1.description)
        self.assertContains(response1, self.price_group2.description)
        self.assertNotContains(response1, self.price_group3.description)

        response2 = self.client.get(
            f"{self.base_url}?publisher__pk__exact={self.price_group3.publisher_id}"
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertNotContains(response2, self.price_group1.description)
        self.assertNotContains(response2, self.price_group2.description)
        self.assertContains(response2, self.price_group3.description)

    def filter_list_by_is_default(self):
        self._create_custom_price_groups()

        response1 = self.client.get(f"{self.base_url}?publisher__isempty=1")
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        for description in self._DEFAULT_GROUP_DESCRIPTIONS:
            self.assertContains(response1, description)
        self.assertNotContains(response1, self.price_group1.description)
        self.assertNotContains(response1, self.price_group2.description)
        self.assertNotContains(response1, self.price_group3.description)

        response2 = self.client.get(f"{self.base_url}?publisher__isempty=0")
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        for description in self._DEFAULT_GROUP_DESCRIPTIONS:
            self.assertNotContains(response2, description)
        self.assertContains(response2, self.price_group1.description)
        self.assertContains(response2, self.price_group2.description)
        self.assertContains(response2, self.price_group3.description)

    def filter_list_by_is_free(self):
        self._create_custom_price_groups()

        free_default_groups = PriceGroup.objects.filter(publisher=None, is_free=True)
        paid_default_groups = PriceGroup.objects.filter(publisher=None, is_free=False)

        response1 = self.client.get(f"{self.base_url}?is_free__exact=1")
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        for default_price_group in free_default_groups:
            self.assertContains(response1, default_price_group.description)

        for default_price_group in paid_default_groups:
            self.assertNotContains(response1, default_price_group.description)

        self.assertNotContains(response1, self.price_group1.description)
        self.assertNotContains(response1, self.price_group2.description)
        self.assertNotContains(response1, self.price_group3.description)

        response2 = self.client.get(f"{self.base_url}?is_free__exact=0")
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        for default_price_group in free_default_groups:
            self.assertNotContains(response2, default_price_group.description)

        for default_price_group in paid_default_groups:
            self.assertContains(response2, default_price_group.description)

        self.assertContains(response2, self.price_group1.description)
        self.assertContains(response2, self.price_group2.description)
        self.assertContains(response2, self.price_group3.description)

    def test_add_price_group(self):
        self.assertEqual(PriceGroup.objects.count(), 8)
        self.assertEqual(PriceGroup.objects.filter(publisher=self.publisher).count(), 0)

        data = {
            "publisher": self.publisher.pk,
            "description_fi": "Alennusryhmä",
            "is_free": False,
        }
        response = self.client.post(f"{self.base_url}add/", data)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(PriceGroup.objects.count(), 9)
        self.assertEqual(PriceGroup.objects.filter(publisher=self.publisher).count(), 1)

        price_group = PriceGroup.objects.filter(publisher=self.publisher).first()
        self.assertEqual(price_group.publisher_id, data["publisher"])
        self.assertEqual(price_group.description, data["description_fi"])
        self.assertEqual(price_group.created_by_id, self.admin.pk)

    def test_cannot_add_price_group_without_publisher(self):
        add_url = f"{self.base_url}add/"

        self.assertEqual(PriceGroup.objects.count(), 8)

        data = {
            "publisher": "",
            "description_fi": "Alennusryhmä",
            "is_free": False,
        }
        response = self.client.post(add_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(PriceGroup.objects.count(), 8)

        data = {
            "description": "New Price Group",
            "is_free": False,
        }
        response = self.client.post(add_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(PriceGroup.objects.count(), 8)

    def test_edit_price_group(self):
        price_group = PriceGroupFactory(
            publisher=self.publisher,
            description="Original",
        )
        self.assertIsNone(price_group.last_modified_by_id)

        self.assertEqual(PriceGroup.objects.count(), 9)
        self.assertEqual(PriceGroup.objects.filter(publisher=self.publisher).count(), 1)

        data = {
            "publisher": self.publisher.pk,
            "description_fi": "Muokattu alennusryhmä",
            "is_free": False,
        }
        response = self.client.post(f"{self.base_url}{price_group.pk}/change/", data)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(PriceGroup.objects.count(), 9)
        self.assertEqual(PriceGroup.objects.filter(publisher=self.publisher).count(), 1)

        price_group.refresh_from_db()
        self.assertEqual(price_group.publisher_id, data["publisher"])
        self.assertEqual(price_group.description, data["description_fi"])
        self.assertEqual(price_group.last_modified_by_id, self.admin.pk)

    def test_delete_price_group(self):
        price_group = PriceGroupFactory()

        self.assertEqual(PriceGroup.objects.count(), 9)

        data = {
            "post": "yes",
        }
        response = self.client.post(f"{self.base_url}{price_group.pk}/delete/", data)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(PriceGroup.objects.count(), 8)

    def test_cannot_edit_default_price_group(self):
        default_price_group = PriceGroup.objects.filter(publisher=None).first()
        self.assertIsNone(default_price_group.publisher)
        self.assertNotEqual(default_price_group.description, "Edited")

        data = {
            "publisher": self.publisher.pk,
            "description_fi": "Muokattu alennusryhmä",
            "is_free": False,
        }
        response = self.client.post(
            f"{self.base_url}{default_price_group.pk}/change/", data
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        default_price_group.refresh_from_db()
        self.assertIsNone(default_price_group.publisher)
        self.assertNotEqual(default_price_group.description, "Edited")

    def test_cannot_delete_default_price_group(self):
        self.assertEqual(PriceGroup.objects.count(), 8)

        default_price_group = PriceGroup.objects.filter(publisher=None).first()

        data = {
            "post": "yes",
        }
        response = self.client.post(
            f"{self.base_url}{default_price_group.pk}/delete/", data
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.assertEqual(PriceGroup.objects.count(), 8)
