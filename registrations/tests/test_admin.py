from decimal import Decimal

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, TestCase
from django.utils import translation
from rest_framework import status

from events.tests.factories import EventFactory, OfferFactory, OrganizationFactory
from registrations.admin import RegistrationAdmin
from registrations.models import (
    Event,
    PriceGroup,
    Registration,
    RegistrationPriceGroup,
    RegistrationUserAccess,
)
from registrations.tests.factories import (
    PriceGroupFactory,
    RegistrationFactory,
    RegistrationPriceGroupFactory,
)
from registrations.tests.utils import assert_invitation_email_is_sent
from registrations.utils import get_signup_create_url

EMAIL = "user@email.com"
EDITED_EMAIL = "user_edited@email.com"
EVENT_NAME = "Foo"


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

        self.client.force_login(self.admin)

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
            "/admin/registrations/registration/add/",
            {
                "event": event2.id,
                "registration_user_accesses-TOTAL_FORMS": 1,
                "registration_user_accesses-INITIAL_FORMS": 0,
                "registration_price_groups-TOTAL_FORMS": 0,
                "registration_price_groups-INITIAL_FORMS": 0,
                "_save": "Save",
            },
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
                    "/admin/registrations/registration/add/",
                    {
                        "event": event.id,
                        "registration_user_accesses-TOTAL_FORMS": 1,
                        "registration_user_accesses-INITIAL_FORMS": 0,
                        "registration_price_groups-TOTAL_FORMS": 0,
                        "registration_price_groups-INITIAL_FORMS": 0,
                    },
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
                    f"/admin/registrations/registration/{self.registration.id}/change/",
                    {
                        "event": self.registration.event.id,
                        "registration_user_accesses-TOTAL_FORMS": 1,
                        "registration_user_accesses-INITIAL_FORMS": 0,
                        "registration_price_groups-TOTAL_FORMS": 0,
                        "registration_price_groups-INITIAL_FORMS": 0,
                    },
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
                "/admin/registrations/registration/add/",
                {
                    "event": event2.id,
                    "registration_user_accesses-TOTAL_FORMS": 2,
                    "registration_user_accesses-INITIAL_FORMS": 0,
                    "registration_user_accesses-0-email": EMAIL,
                    "registration_user_accesses-1-email": EMAIL,
                    "registration_price_groups-TOTAL_FORMS": 0,
                    "registration_price_groups-INITIAL_FORMS": 0,
                    "_save": "Save",
                },
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
                "/admin/registrations/registration/add/",
                {
                    "event": event2.id,
                    "registration_user_accesses-TOTAL_FORMS": 1,
                    "registration_user_accesses-INITIAL_FORMS": 0,
                    "registration_user_accesses-0-email": EMAIL,
                    "registration_price_groups-TOTAL_FORMS": 0,
                    "registration_price_groups-INITIAL_FORMS": 0,
                    "_save": "Save",
                },
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
                f"/admin/registrations/registration/{self.registration.id}/change/",
                {
                    "event": self.registration.event.id,
                    "registration_user_accesses-TOTAL_FORMS": 2,
                    "registration_user_accesses-INITIAL_FORMS": 1,
                    "registration_user_accesses-0-email": EDITED_EMAIL,
                    "registration_user_accesses-0-id": registration_user_access.id,
                    "registration_user_accesses-0-registration": self.registration.id,
                    "registration_price_groups-TOTAL_FORMS": 0,
                    "registration_price_groups-INITIAL_FORMS": 0,
                    "_save": "Save",
                },
            )

            assert response.status_code == status.HTTP_302_FOUND
            assert response.url == "/admin/registrations/registration/"

            # Assert that invitation is sent to updated email
            registration_user_access.refresh_from_db()
            assert_invitation_email_is_sent(
                EDITED_EMAIL, EVENT_NAME, registration_user_access
            )

    def test_add_new_registration_with_price_groups(self):
        data_source = self.registration.event.data_source
        publisher = self.registration.event.publisher
        event2 = Event.objects.create(
            id="event-2", data_source=data_source, publisher=publisher
        )

        price_group = PriceGroupFactory(description="Adults")
        price_group2 = PriceGroupFactory(description="Children")

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

        response = self.client.post(
            "/admin/registrations/registration/add/",
            {
                "event": event2.id,
                "registration_user_accesses-TOTAL_FORMS": 0,
                "registration_user_accesses-INITIAL_FORMS": 0,
                "registration_price_groups-TOTAL_FORMS": 2,
                "registration_price_groups-INITIAL_FORMS": 0,
                "registration_price_groups-0-price_group": price_group.pk,
                "registration_price_groups-0-price": Decimal("10"),
                "registration_price_groups-0-vat_percentage": RegistrationPriceGroup.VatPercentage.VAT_24,
                "registration_price_groups-1-price_group": price_group2.pk,
                "registration_price_groups-1-price": Decimal("5"),
                "registration_price_groups-1-vat_percentage": RegistrationPriceGroup.VatPercentage.VAT_10,
            },
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
        self.assertEqual(registration_price_group.price_group_id, price_group.pk)
        self.assertEqual(registration_price_group.price, Decimal("10"))
        self.assertEqual(
            registration_price_group.vat_percentage,
            RegistrationPriceGroup.VatPercentage.VAT_24,
        )
        self.assertEqual(registration_price_group.price_without_vat, Decimal("8.06"))
        self.assertEqual(registration_price_group.vat, Decimal("1.94"))

        registration_price_group2 = RegistrationPriceGroup.objects.last()
        self.assertEqual(registration_price_group2.price_group_id, price_group2.pk)
        self.assertEqual(registration_price_group2.price, Decimal("5"))
        self.assertEqual(
            registration_price_group2.vat_percentage,
            RegistrationPriceGroup.VatPercentage.VAT_10,
        )
        self.assertEqual(registration_price_group2.price_without_vat, Decimal("4.55"))
        self.assertEqual(registration_price_group2.vat, Decimal("0.45"))

    def test_add_price_groups_to_existing_registration(self):
        price_group = PriceGroupFactory(description="Adults")
        price_group2 = PriceGroupFactory(description="Children")

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

        response = self.client.post(
            f"/admin/registrations/registration/{self.registration.pk}/change/",
            {
                "event": self.registration.event.id,
                "registration_user_accesses-TOTAL_FORMS": 1,
                "registration_user_accesses-INITIAL_FORMS": 0,
                "registration_price_groups-TOTAL_FORMS": 2,
                "registration_price_groups-INITIAL_FORMS": 0,
                "registration_price_groups-0-registration": self.registration.id,
                "registration_price_groups-0-price_group": price_group.pk,
                "registration_price_groups-0-price": Decimal("10"),
                "registration_price_groups-0-vat_percentage": RegistrationPriceGroup.VatPercentage.VAT_14,
                "registration_price_groups-1-registration": self.registration.id,
                "registration_price_groups-1-price_group": price_group2.pk,
                "registration_price_groups-1-price": Decimal("5"),
                "registration_price_groups-1-vat_percentage": RegistrationPriceGroup.VatPercentage.VAT_0,
            },
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
        self.assertEqual(registration_price_group.price_group_id, price_group.pk)
        self.assertEqual(registration_price_group.price, Decimal("10"))
        self.assertEqual(
            registration_price_group.vat_percentage,
            RegistrationPriceGroup.VatPercentage.VAT_14,
        )
        self.assertEqual(registration_price_group.price_without_vat, Decimal("8.77"))
        self.assertEqual(registration_price_group.vat, Decimal("1.23"))

        registration_price_group2 = RegistrationPriceGroup.objects.last()
        self.assertEqual(registration_price_group2.price_group_id, price_group2.pk)
        self.assertEqual(registration_price_group2.price, Decimal("5"))
        self.assertEqual(
            registration_price_group2.vat_percentage,
            RegistrationPriceGroup.VatPercentage.VAT_0,
        )
        self.assertEqual(registration_price_group2.price_without_vat, Decimal("5"))
        self.assertEqual(registration_price_group2.vat, Decimal("0"))

    def test_cannot_add_duplicate_price_groups_to_registration(self):
        price_group = PriceGroupFactory(description="Adults")

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

        response = self.client.post(
            f"/admin/registrations/registration/{self.registration.pk}/change/",
            {
                "event": self.registration.event.id,
                "registration_user_accesses-TOTAL_FORMS": 1,
                "registration_user_accesses-INITIAL_FORMS": 0,
                "registration_price_groups-TOTAL_FORMS": 2,
                "registration_price_groups-INITIAL_FORMS": 0,
                "registration_price_groups-0-registration": self.registration.id,
                "registration_price_groups-0-price_group": price_group.pk,
                "registration_price_groups-0-price": Decimal("10"),
                "registration_price_groups-0-vat_percentage": RegistrationPriceGroup.VatPercentage.VAT_24,
                "registration_price_groups-1-registration": self.registration.id,
                "registration_price_groups-1-price_group": price_group.pk,
                "registration_price_groups-1-price": Decimal("5"),
                "registration_price_groups-1-vat_percentage": RegistrationPriceGroup.VatPercentage.VAT_24,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

    def test_cannot_use_more_than_two_decimals_for_registration_price_group_price(self):
        price_group = PriceGroupFactory(description="Adults")

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

        response = self.client.post(
            f"/admin/registrations/registration/{self.registration.pk}/change/",
            {
                "event": self.registration.event.id,
                "registration_user_accesses-TOTAL_FORMS": 1,
                "registration_user_accesses-INITIAL_FORMS": 0,
                "registration_price_groups-TOTAL_FORMS": 2,
                "registration_price_groups-INITIAL_FORMS": 0,
                "registration_price_groups-0-registration": self.registration.id,
                "registration_price_groups-0-price_group": price_group.pk,
                "registration_price_groups-0-price": Decimal("10.123"),
                "registration_price_groups-0-vat_percentage": RegistrationPriceGroup.VatPercentage.VAT_24,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)

    def test_delete_price_group_from_registration(self):
        registration_price_group = RegistrationPriceGroupFactory(
            registration=self.registration,
            price=Decimal("10"),
        )

        self.assertEqual(RegistrationPriceGroup.objects.count(), 1)

        response = self.client.post(
            f"/admin/registrations/registration/{self.registration.pk}/change/",
            {
                "event": self.registration.event.id,
                "registration_user_accesses-TOTAL_FORMS": 1,
                "registration_user_accesses-INITIAL_FORMS": 0,
                "registration_price_groups-TOTAL_FORMS": 1,
                "registration_price_groups-INITIAL_FORMS": 1,
                "registration_price_groups-0-id": registration_price_group.id,
                "registration_price_groups-0-registration": self.registration.id,
                "registration_price_groups-0-price_group": registration_price_group.price_group_id,
                "registration_price_groups-0-price": Decimal("10"),
                "registration_price_groups-0-vat_percentage": RegistrationPriceGroup.VatPercentage.VAT_24,
                "registration_price_groups-0-DELETE": "on",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)

        self.assertEqual(RegistrationPriceGroup.objects.count(), 0)


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
