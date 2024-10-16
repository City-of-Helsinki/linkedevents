from collections import Counter
from decimal import Decimal
from uuid import uuid4

import pytest
import requests_mock
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase

from events.models import Event, Language, PublicationStatus
from events.tests.factories import (
    DataSourceFactory,
    EventFactory,
    LanguageFactory,
    OrganizationFactory,
)
from helevents.tests.factories import UserFactory
from registrations.enums import VatPercentage
from registrations.exceptions import PriceGroupValidationError
from registrations.models import (
    VAT_CODE_MAPPING,
    RegistrationPriceGroup,
    RegistrationWebStoreProductMapping,
    SignUp,
    WebStoreAccount,
    WebStoreMerchant,
    web_store_price_group_meta_key,
)
from registrations.notifications import SignUpNotificationType
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    RegistrationWebStoreAccountFactory,
    RegistrationWebStoreMerchantFactory,
    RegistrationWebStoreProductMappingFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpGroupProtectedDataFactory,
    SignUpPaymentCancellationFactory,
    SignUpPaymentFactory,
    SignUpPaymentRefundFactory,
    SignUpPriceGroupFactory,
    SignUpProtectedDataFactory,
    WebStoreAccountFactory,
    WebStoreMerchantFactory,
)
from registrations.utils import strip_trailing_zeroes_from_decimal
from web_store.tests.product.test_web_store_product_api_client import (
    DEFAULT_GET_PRODUCT_MAPPING_DATA,
    DEFAULT_PRODUCT_ID,
)

contact_person_data = {
    "email": "test@email.com",
    "first_name": "Contact first name",
    "last_name": "Contact last name",
    "membership_number": "xxx",
    "phone_number": "044 1234567",
}

signup_group_data = {"protected_data": {"extra_info": "Group extra info"}}

signup_data = {
    "city": "City",
    "first_name": "First name",
    "last_name": "Last name",
    "street_address": "Street address 12",
    "zipcode": "12345",
    "protected_data": {
        "date_of_birth": "2012-12-12",
        "extra_info": "Extra info",
    },
}

anonymize_replacement = "<DELETED>"


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

    def test_get_waitlisted(self):
        signup = SignUpFactory(
            registration=self.registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )
        signup2 = SignUpFactory(
            registration=self.registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )
        signup3 = SignUpFactory(
            registration=self.registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        )
        SignUpFactory(
            registration=self.registration,
            attendee_status=SignUp.AttendeeStatus.ATTENDING,
        )
        signups = SignUp.objects.filter(
            pk__in=[signup.pk, signup2.pk, signup3.pk]
        ).order_by("id")

        for count in [1, 2, 3]:
            with self.subTest():
                self.assertQuerySetEqual(
                    signups[:count],
                    self.registration.get_waitlisted(count=count),
                )

    def test_get_waitlisted_count_valueerror(self):
        for count in [None, -1, 0]:
            with self.subTest():
                with pytest.raises(
                    ValueError, match="get_waitlisted: count must be at least 1"
                ):
                    self.registration.get_waitlisted(count=count)

    def test_has_payments_with_signups(self):
        self.assertFalse(self.registration.has_payments)

        SignUpPaymentFactory(signup__registration=self.registration)

        self.assertTrue(self.registration.has_payments)

    def test_has_payments_with_signup_groups(self):
        self.assertFalse(self.registration.has_payments)

        SignUpPaymentFactory(
            signup=None,
            signup_group=SignUpGroupFactory(registration=self.registration),
        )

        self.assertTrue(self.registration.has_payments)

    def test_create_or_update_web_store_product_mapping_and_accounting(self):
        with self.settings(WEB_STORE_INTEGRATION_ENABLED=False):
            RegistrationWebStoreMerchantFactory(
                registration=self.registration,
            )
        RegistrationWebStoreAccountFactory(registration=self.registration)

        product_url = f"{settings.WEB_STORE_API_BASE_URL}product/"
        accounting_url = f"{product_url}{DEFAULT_PRODUCT_ID}/accounting"

        for vat_percentage in [vat.value for vat in VatPercentage]:
            with self.subTest(), requests_mock.Mocker() as req_mock:
                RegistrationPriceGroupFactory(
                    registration=self.registration, vat_percentage=vat_percentage
                )

                req_mock.post(product_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
                req_mock.post(accounting_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)

                self.registration.create_or_update_web_store_product_mapping_and_accounting()

                self.assertEqual(req_mock.call_count, 2)
                self.assertEqual(RegistrationWebStoreProductMapping.objects.count(), 1)
                self.assertEqual(
                    RegistrationWebStoreProductMapping.objects.filter(
                        registration=self.registration,
                        external_product_id=DEFAULT_PRODUCT_ID,
                        vat_code=VAT_CODE_MAPPING[vat_percentage],
                    ).count(),
                    1,
                )

                RegistrationWebStoreProductMapping.objects.all().delete()
                RegistrationPriceGroup.objects.all().delete()

    def test_get_calendar_events(self):
        events = self.registration.get_calendar_events()
        self.assertListEqual(events, [self.registration.event])

    def test_get_calendar_events_with_recurring_event(self):
        self.registration.event.super_event_type = Event.SuperEventType.RECURRING
        self.registration.event.save(update_fields=["super_event_type"])

        # Published and scheduled sub-events that should be included.
        sub_event1 = EventFactory(
            super_event=self.registration.event,
            name_fi="Event 1",
        )
        sub_event2 = EventFactory(
            super_event=self.registration.event,
            name_fi="Event 2",
        )

        # Published and re-scheduled sub-event that should be included.
        sub_event3 = EventFactory(
            super_event=self.registration.event,
            name_fi="Event 3",
            event_status=Event.Status.RESCHEDULED,
        )

        # A draft sub-event that should not be included.
        EventFactory(
            super_event=self.registration.event,
            name_fi="Event 3",
            publication_status=PublicationStatus.DRAFT,
        )

        # A cancelled sub-event that should not be included.
        EventFactory(
            super_event=self.registration.event,
            name_fi="Event 4",
            event_status=Event.Status.CANCELLED,
        )

        # A postponed sub-event that should not be included.
        EventFactory(
            super_event=self.registration.event,
            name_fi="Event 5",
            event_status=Event.Status.POSTPONED,
        )

        events = self.registration.get_calendar_events()
        self.assertEqual(
            Counter(list(events)), Counter([sub_event1, sub_event2, sub_event3])
        )


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

    def test_signup_group_data_is_anonymized(self):
        registration = RegistrationFactory()
        user = UserFactory()
        signup_group = SignUpGroupFactory(
            registration=registration,
            created_by=user,
            last_modified_by=user,
        )
        signup_group_protected_data = SignUpGroupProtectedDataFactory(
            signup_group=signup_group,
            registration=registration,
            extra_info=signup_group_data["protected_data"]["extra_info"],
        )
        contact_person = SignUpContactPersonFactory(
            signup_group=signup_group,
            email=contact_person_data["email"],
            first_name=contact_person_data["first_name"],
            last_name=contact_person_data["last_name"],
            membership_number=contact_person_data["membership_number"],
            phone_number=contact_person_data["phone_number"],
        )
        signup = SignUpFactory(
            created_by=user,
            last_modified_by=user,
            street_address=signup_data["street_address"],
            city=signup_data["city"],
            zipcode=signup_data["zipcode"],
            first_name=signup_data["first_name"],
            last_name=signup_data["last_name"],
            registration=registration,
            signup_group=signup_group,
        )
        signup_protected_data = SignUpProtectedDataFactory(
            signup=signup,
            registration=signup.registration,
            date_of_birth=signup_data["protected_data"]["date_of_birth"],
            extra_info=signup_data["protected_data"]["extra_info"],
        )

        assert signup_group.anonymization_time is None
        assert signup_group.created_by == user
        assert signup_group.last_modified_by == user
        assert signup.anonymization_time is None
        assert signup.created_by == user
        assert signup.last_modified_by == user

        signup_group.anonymize()

        # Signup group should be anonymized
        assert signup_group_protected_data.extra_info is None
        assert contact_person.email == anonymize_replacement
        assert contact_person.first_name == anonymize_replacement
        assert contact_person.last_name == anonymize_replacement
        assert contact_person.membership_number == anonymize_replacement
        assert contact_person.phone_number == anonymize_replacement
        assert signup_group.anonymization_time is not None
        assert signup_group.created_by is None
        assert signup_group.last_modified_by is None

        # Signup should be anonymized
        signup.refresh_from_db()
        signup_protected_data.refresh_from_db()
        # City and zipcode are not anonymized
        assert signup.city == signup_data["city"]
        assert signup.zipcode == signup_data["zipcode"]
        # All other signup fields are anonymized
        assert signup.first_name == anonymize_replacement
        assert signup.last_name == anonymize_replacement
        assert signup.street_address == anonymize_replacement
        # Date of birth is not anonymized
        assert (
            str(signup_protected_data.date_of_birth)
            == signup_data["protected_data"]["date_of_birth"]
        )
        # Extra info is anonymized
        assert signup_protected_data.extra_info is None
        assert signup.anonymization_time is not None
        assert signup.created_by is None
        assert signup.last_modified_by is None

    def test_to_web_store_order_json(self):
        product_mapping = RegistrationWebStoreProductMappingFactory(
            registration=self.signup_group.registration
        )

        english = LanguageFactory(pk="en", service_language=True)

        contact_person = SignUpContactPersonFactory(
            signup_group=self.signup_group,
            first_name="Mickey",
            last_name="Mouse",
            email="mickey@test.com",
            phone_number="+35811111111",
            service_language=english,
        )

        signup = SignUpFactory(
            registration=self.signup_group.registration,
            signup_group=self.signup_group,
        )

        price_group = SignUpPriceGroupFactory(signup=signup)
        price_group.refresh_from_db()
        price_net = str(
            strip_trailing_zeroes_from_decimal(price_group.price_without_vat)
        )
        price_vat = str(strip_trailing_zeroes_from_decimal(price_group.vat))
        price_total = str(strip_trailing_zeroes_from_decimal(price_group.price))

        signup2 = SignUpFactory(
            registration=self.signup_group.registration,
            signup_group=self.signup_group,
        )

        price_group2 = SignUpPriceGroupFactory(
            signup=signup2,
            registration_price_group__vat_percentage=VatPercentage.VAT_10.value,
        )
        price_group2.refresh_from_db()
        price_net2 = str(
            strip_trailing_zeroes_from_decimal(price_group2.price_without_vat)
        )
        price_vat2 = str(strip_trailing_zeroes_from_decimal(price_group2.vat))
        price_total2 = str(strip_trailing_zeroes_from_decimal(price_group2.price))

        self.assertDictEqual(
            self.signup_group.to_web_store_order_json(self.user.uuid),
            {
                "namespace": settings.WEB_STORE_API_NAMESPACE,
                "user": str(self.user.uuid),
                "items": [
                    {
                        "productId": product_mapping.external_product_id,
                        "productName": price_group.description_en,
                        "quantity": 1,
                        "unit": "pcs",
                        "rowPriceNet": price_net,
                        "rowPriceVat": price_vat,
                        "rowPriceTotal": price_total,
                        "priceNet": price_net,
                        "priceGross": price_total,
                        "priceVat": price_vat,
                        "vatPercentage": str(
                            strip_trailing_zeroes_from_decimal(
                                price_group.vat_percentage
                            )
                        ),
                        "meta": [
                            {
                                "key": web_store_price_group_meta_key,
                                "value": str(price_group.pk),
                                "visibleInCheckout": False,
                                "ordinal": "0",
                            }
                        ],
                    },
                    {
                        "productId": product_mapping.external_product_id,
                        "productName": price_group2.description_en,
                        "quantity": 1,
                        "unit": "pcs",
                        "rowPriceNet": price_net2,
                        "rowPriceVat": price_vat2,
                        "rowPriceTotal": price_total2,
                        "priceNet": price_net2,
                        "priceGross": price_total2,
                        "priceVat": price_vat2,
                        "vatPercentage": str(
                            strip_trailing_zeroes_from_decimal(
                                price_group2.vat_percentage
                            )
                        ),
                        "meta": [
                            {
                                "key": web_store_price_group_meta_key,
                                "value": str(price_group2.pk),
                                "visibleInCheckout": False,
                                "ordinal": "0",
                            },
                            {
                                "key": "eventName",
                                "value": self.signup_group.registration.event.name,
                                "label": self.signup_group.web_store_meta_label,
                                "visibleInCheckout": True,
                                "ordinal": "1",
                            },
                        ],
                    },
                ],
                "priceNet": str(
                    strip_trailing_zeroes_from_decimal(
                        price_group.price_without_vat + price_group2.price_without_vat
                    )
                ),
                "priceVat": str(
                    strip_trailing_zeroes_from_decimal(
                        price_group.vat + price_group2.vat
                    )
                ),
                "priceTotal": str(
                    strip_trailing_zeroes_from_decimal(
                        price_group.price + price_group2.price
                    )
                ),
                "customer": {
                    "firstName": contact_person.first_name,
                    "lastName": contact_person.last_name,
                    "email": contact_person.email,
                    "phone": contact_person.phone_number,
                },
                "language": contact_person.service_language_id,
            },
        )

    def test_to_web_store_order_json_missing_price_group(self):
        english = LanguageFactory(pk="en", service_language=True)

        SignUpContactPersonFactory(
            signup_group=self.signup_group,
            first_name="Mickey",
            last_name="Mouse",
            email="mickey@test.com",
            phone_number="+35811111111",
            service_language=english,
        )

        SignUpFactory(
            registration=self.signup_group.registration,
            signup_group=self.signup_group,
        )

        with self.assertRaises(PriceGroupValidationError) as exc:
            self.signup_group.to_web_store_order_json(self.user.uuid)
        self.assertEqual(
            exc.exception.messages[0], "No price groups exist for signup group."
        )

    def test_soft_delete(self):
        signup = SignUpFactory(
            registration=self.signup_group.registration, signup_group=self.signup_group
        )
        signup2 = SignUpFactory(
            registration=self.signup_group.registration, signup_group=self.signup_group
        )
        contact_person = SignUpContactPersonFactory(signup_group=self.signup_group)
        protected_data = SignUpGroupProtectedDataFactory(signup_group=self.signup_group)
        payment = SignUpPaymentFactory(signup_group=self.signup_group, signup=None)
        payment_refund = SignUpPaymentRefundFactory(
            payment=payment, signup_group=self.signup_group
        )
        payment_cancellation = SignUpPaymentCancellationFactory(
            payment=payment, signup_group=self.signup_group
        )

        self.assertFalse(self.signup_group.deleted)
        self.assertIsNone(self.signup_group.last_modified_by)
        signup_group_last_modified_time = self.signup_group.last_modified_time

        self.assertFalse(signup.deleted)
        self.assertIsNone(signup.last_modified_by)
        signup_last_modified_time = signup.last_modified_time

        self.assertFalse(signup2.deleted)
        self.assertIsNone(signup2.last_modified_by)
        signup2_last_modified_time = signup2.last_modified_time

        self.assertFalse(contact_person.deleted)
        self.assertFalse(protected_data.deleted)

        self.assertFalse(payment.deleted)
        self.assertIsNone(payment.last_modified_by)
        payment_last_modified_time = payment.last_modified_time

        self.assertFalse(payment_refund.deleted)

        self.signup_group.last_modified_by = self.user
        self.signup_group.soft_delete()

        self.signup_group.refresh_from_db()
        signup.refresh_from_db()
        signup2.refresh_from_db()
        contact_person.refresh_from_db()
        protected_data.refresh_from_db()
        payment.refresh_from_db()
        payment_refund.refresh_from_db()
        payment_cancellation.refresh_from_db()

        self.assertTrue(self.signup_group.deleted)
        self.assertEqual(self.signup_group.last_modified_by_id, self.user.pk)
        self.assertTrue(
            self.signup_group.last_modified_time > signup_group_last_modified_time
        )

        self.assertTrue(signup.deleted)
        self.assertEqual(signup.last_modified_by_id, self.user.pk)
        self.assertTrue(signup.last_modified_time > signup_last_modified_time)

        self.assertTrue(signup2.deleted)
        self.assertEqual(signup2.last_modified_by_id, self.user.pk)
        self.assertTrue(signup2.last_modified_time > signup2_last_modified_time)

        self.assertTrue(contact_person.deleted)
        self.assertTrue(protected_data.deleted)

        self.assertTrue(payment.deleted)
        self.assertEqual(payment.last_modified_by_id, self.user.pk)
        self.assertTrue(payment.last_modified_time > payment_last_modified_time)

        self.assertTrue(payment_refund.deleted)

        self.assertTrue(payment_cancellation.deleted)

    def test_undelete(self):
        self.signup_group.deleted = True
        self.signup_group.save(update_fields=["deleted"])

        signup = SignUpFactory(
            registration=self.signup_group.registration,
            signup_group=self.signup_group,
            deleted=True,
        )
        signup2 = SignUpFactory(
            registration=self.signup_group.registration,
            signup_group=self.signup_group,
            deleted=True,
        )
        contact_person = SignUpContactPersonFactory(
            signup_group=self.signup_group, deleted=True
        )
        protected_data = SignUpGroupProtectedDataFactory(
            signup_group=self.signup_group, deleted=True
        )
        payment = SignUpPaymentFactory(
            signup_group=self.signup_group,
            signup=None,
            deleted=True,
        )
        payment_refund = SignUpPaymentRefundFactory(
            payment=payment,
            signup_group=self.signup_group,
            deleted=True,
        )
        payment_cancellation = SignUpPaymentCancellationFactory(
            payment=payment,
            signup_group=self.signup_group,
            deleted=True,
        )

        self.assertTrue(self.signup_group.deleted)
        self.assertIsNone(self.signup_group.last_modified_by)
        signup_group_last_modified_time = self.signup_group.last_modified_time

        self.assertTrue(signup.deleted)
        self.assertIsNone(signup.last_modified_by)
        signup_last_modified_time = signup.last_modified_time

        self.assertTrue(signup2.deleted)
        self.assertIsNone(signup2.last_modified_by)
        signup2_last_modified_time = signup2.last_modified_time

        self.assertTrue(contact_person.deleted)
        self.assertTrue(protected_data.deleted)

        self.assertTrue(payment.deleted)
        self.assertIsNone(payment.last_modified_by)
        payment_last_modified_time = payment.last_modified_time

        self.assertTrue(payment_refund.deleted)

        self.signup_group.last_modified_by = self.user
        self.signup_group.undelete()

        self.signup_group.refresh_from_db()
        signup.refresh_from_db()
        signup2.refresh_from_db()
        contact_person.refresh_from_db()
        protected_data.refresh_from_db()
        payment.refresh_from_db()
        payment_refund.refresh_from_db()
        payment_cancellation.refresh_from_db()

        self.assertFalse(self.signup_group.deleted)
        self.assertEqual(self.signup_group.last_modified_by_id, self.user.pk)
        self.assertTrue(
            self.signup_group.last_modified_time > signup_group_last_modified_time
        )

        self.assertFalse(signup.deleted)
        self.assertEqual(signup.last_modified_by_id, self.user.pk)
        self.assertTrue(signup.last_modified_time > signup_last_modified_time)

        self.assertFalse(signup2.deleted)
        self.assertEqual(signup2.last_modified_by_id, self.user.pk)
        self.assertTrue(signup2.last_modified_time > signup2_last_modified_time)

        self.assertFalse(contact_person.deleted)
        self.assertFalse(protected_data.deleted)

        self.assertFalse(payment.deleted)
        self.assertEqual(payment.last_modified_by_id, self.user.pk)
        self.assertTrue(payment.last_modified_time > payment_last_modified_time)

        self.assertFalse(payment_refund.deleted)

        self.assertFalse(payment_cancellation.deleted)

    def test_price_groups(self):
        price_group = SignUpPriceGroupFactory(
            signup__signup_group=self.signup_group,
            signup__registration=self.signup_group.registration,
        )
        price_group2 = SignUpPriceGroupFactory(
            signup__signup_group=self.signup_group,
            signup__registration=self.signup_group.registration,
        )

        # Third price group doesn't belong to the signup group.
        SignUpPriceGroupFactory(signup__registration=self.signup_group.registration)

        self.assertEqual(
            Counter(self.signup_group.price_groups),
            Counter([price_group, price_group2]),
        )

    def test_price_groups_is_empty_list(self):
        self.assertEqual(len(self.signup_group.price_groups), 0)


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

    def test_full_name(self):
        for first_name, last_name, expected in (
            ("Firstname", "Lastname", "Firstname Lastname"),
            ("", "", ""),
            (" ", " ", ""),
            (None, None, ""),
            ("Firstname", "", "Firstname"),
            ("Firstname", None, "Firstname"),
            ("Firstname", " ", "Firstname"),
            ("", "Lastname", "Lastname"),
            (None, "Lastname", "Lastname"),
            (" ", "Lastname", "Lastname"),
        ):
            with self.subTest():
                self.signup.first_name = first_name
                self.signup.last_name = last_name
                self.signup.save(update_fields=["first_name", "last_name"])

                self.signup.refresh_from_db()

                self.assertEqual(self.signup.full_name, expected)

    def test_actual_contact_person_with_group(self):
        signup_group = SignUpGroupFactory(registration=self.signup.registration)
        contact_person = SignUpContactPersonFactory(signup_group=signup_group)
        self.signup.signup_group = signup_group
        self.signup.save(update_fields=["signup_group"])

        self.signup.refresh_from_db()

        assert self.signup.actual_contact_person.pk == contact_person.pk

    def test_actual_contact_person_without_group(self):
        contact_person = SignUpContactPersonFactory(signup=self.signup)

        self.signup.refresh_from_db()

        assert self.signup.actual_contact_person.pk == contact_person.pk

    def test_signup_data_is_anonymisized(self):
        user = UserFactory()
        signup = SignUpFactory(
            created_by=user,
            last_modified_by=user,
            street_address=signup_data["street_address"],
            city=signup_data["city"],
            zipcode=signup_data["zipcode"],
            first_name=signup_data["first_name"],
            last_name=signup_data["last_name"],
        )
        contact_person = SignUpContactPersonFactory(
            signup=signup,
            email=contact_person_data["email"],
            first_name=contact_person_data["first_name"],
            last_name=contact_person_data["last_name"],
            membership_number=contact_person_data["membership_number"],
            phone_number=contact_person_data["phone_number"],
        )
        protected_data = SignUpProtectedDataFactory(
            signup=signup,
            registration=signup.registration,
            date_of_birth=signup_data["protected_data"]["date_of_birth"],
            extra_info=signup_data["protected_data"]["extra_info"],
        )

        assert signup.anonymization_time is None
        assert signup.created_by == user
        assert signup.last_modified_by == user

        signup.anonymize()

        # City and zipcode are not anonymized
        assert signup.city == signup_data["city"]
        assert signup.zipcode == signup_data["zipcode"]
        # All other signup fields are anonymized
        assert signup.first_name == anonymize_replacement
        assert signup.last_name == anonymize_replacement
        assert signup.street_address == anonymize_replacement
        # All contact person fields are anonymized
        assert contact_person.email == anonymize_replacement
        assert contact_person.first_name == anonymize_replacement
        assert contact_person.last_name == anonymize_replacement
        assert contact_person.membership_number == anonymize_replacement
        assert contact_person.phone_number == anonymize_replacement
        # Date of birth is not anonymized
        assert (
            str(protected_data.date_of_birth)
            == signup_data["protected_data"]["date_of_birth"]
        )
        # Extra info is anonymized
        assert protected_data.extra_info is None
        assert signup.anonymization_time is not None
        assert signup.created_by is None
        assert signup.last_modified_by is None

    def test_to_web_store_order_json(self):
        product_mapping = RegistrationWebStoreProductMappingFactory(
            registration=self.signup.registration
        )

        english = LanguageFactory(pk="en", service_language=True)

        contact_person = SignUpContactPersonFactory(
            signup=self.signup,
            first_name="Mickey",
            last_name="Mouse",
            email="mickey@test.com",
            phone_number="+35811111111",
            service_language=english,
        )
        price_group = SignUpPriceGroupFactory(signup=self.signup)

        price_net = str(
            strip_trailing_zeroes_from_decimal(price_group.price_without_vat)
        )
        price_vat = str(strip_trailing_zeroes_from_decimal(price_group.vat))
        price_total = str(strip_trailing_zeroes_from_decimal(price_group.price))

        self.assertDictEqual(
            self.signup.to_web_store_order_json(self.user.uuid),
            {
                "namespace": settings.WEB_STORE_API_NAMESPACE,
                "user": str(self.user.uuid),
                "items": [
                    {
                        "productId": product_mapping.external_product_id,
                        "productName": price_group.description_en,
                        "quantity": 1,
                        "unit": "pcs",
                        "rowPriceNet": price_net,
                        "rowPriceVat": price_vat,
                        "rowPriceTotal": price_total,
                        "priceNet": price_net,
                        "priceGross": price_total,
                        "priceVat": price_vat,
                        "vatPercentage": str(
                            strip_trailing_zeroes_from_decimal(
                                price_group.vat_percentage
                            )
                        ),
                        "meta": [
                            {
                                "key": web_store_price_group_meta_key,
                                "value": str(price_group.pk),
                                "visibleInCheckout": False,
                                "ordinal": "0",
                            },
                            {
                                "key": "eventName",
                                "value": self.signup.registration.event.name,
                                "label": self.signup.web_store_meta_label,
                                "visibleInCheckout": True,
                                "ordinal": "1",
                            },
                        ],
                    },
                ],
                "priceNet": price_net,
                "priceVat": price_vat,
                "priceTotal": price_total,
                "language": contact_person.service_language_id,
                "customer": {
                    "firstName": contact_person.first_name,
                    "lastName": contact_person.last_name,
                    "email": contact_person.email,
                    "phone": contact_person.phone_number,
                },
            },
        )

    def test_to_web_store_order_json_missing_price_group(self):
        english = LanguageFactory(pk="en", service_language=True)

        SignUpContactPersonFactory(
            signup=self.signup,
            first_name="Mickey",
            last_name="Mouse",
            email="mickey@test.com",
            phone_number="+35811111111",
            service_language=english,
        )

        with self.assertRaises(PriceGroupValidationError) as exc:
            self.signup.to_web_store_order_json(self.user.uuid)

        self.assertEqual(
            exc.exception.messages[0], "Price group does not exist for signup."
        )

    def test_soft_delete(self):
        contact_person = SignUpContactPersonFactory(signup=self.signup)
        protected_data = SignUpProtectedDataFactory(signup=self.signup)
        price_group = SignUpPriceGroupFactory(signup=self.signup)
        payment = SignUpPaymentFactory(signup=self.signup)
        payment_refund = SignUpPaymentRefundFactory(payment=payment, signup=self.signup)
        payment_cancellation = SignUpPaymentCancellationFactory(
            payment=payment, signup=self.signup
        )

        self.assertFalse(self.signup.deleted)
        self.assertIsNone(self.signup.last_modified_by)
        signup_last_modified_time = self.signup.last_modified_time

        self.assertFalse(contact_person.deleted)
        self.assertFalse(protected_data.deleted)
        self.assertFalse(price_group.deleted)

        self.assertFalse(payment.deleted)
        self.assertIsNone(payment.last_modified_by)
        payment_last_modified_time = payment.last_modified_time

        self.assertFalse(payment_refund.deleted)

        self.assertFalse(payment_cancellation.deleted)

        self.signup.last_modified_by = self.user
        self.signup.soft_delete()

        self.signup.refresh_from_db()
        contact_person.refresh_from_db()
        protected_data.refresh_from_db()
        price_group.refresh_from_db()
        payment.refresh_from_db()
        payment_refund.refresh_from_db()
        payment_cancellation.refresh_from_db()

        self.assertTrue(self.signup.deleted)
        self.assertEqual(self.signup.last_modified_by_id, self.user.pk)
        self.assertTrue(self.signup.last_modified_time > signup_last_modified_time)

        self.assertTrue(contact_person.deleted)
        self.assertTrue(protected_data.deleted)
        self.assertTrue(price_group.deleted)

        self.assertTrue(payment.deleted)
        self.assertEqual(payment.last_modified_by_id, self.user.pk)
        self.assertTrue(payment.last_modified_time > payment_last_modified_time)

        self.assertTrue(payment_refund.deleted)

        self.assertTrue(payment_cancellation.deleted)

    def test_undelete(self):
        self.signup.deleted = True
        self.signup.save(update_fields=["deleted"])

        contact_person = SignUpContactPersonFactory(signup=self.signup, deleted=True)
        protected_data = SignUpProtectedDataFactory(signup=self.signup, deleted=True)
        price_group = SignUpPriceGroupFactory(signup=self.signup, deleted=True)
        payment = SignUpPaymentFactory(signup=self.signup, deleted=True)
        payment_refund = SignUpPaymentRefundFactory(
            payment=payment, signup=self.signup, deleted=True
        )
        payment_cancellation = SignUpPaymentCancellationFactory(
            payment=payment, signup=self.signup, deleted=True
        )

        self.assertTrue(self.signup.deleted)
        self.assertIsNone(self.signup.last_modified_by)
        signup_last_modified_time = self.signup.last_modified_time

        self.assertTrue(contact_person.deleted)
        self.assertTrue(protected_data.deleted)
        self.assertTrue(price_group.deleted)

        self.assertTrue(payment.deleted)
        self.assertIsNone(payment.last_modified_by)
        payment_last_modified_time = payment.last_modified_time

        self.assertTrue(payment_refund.deleted)

        self.assertTrue(payment_cancellation.deleted)

        self.signup.last_modified_by = self.user
        self.signup.undelete()

        self.signup.refresh_from_db()
        contact_person.refresh_from_db()
        protected_data.refresh_from_db()
        price_group.refresh_from_db()
        payment.refresh_from_db()
        payment_refund.refresh_from_db()
        payment_cancellation.refresh_from_db()

        self.assertFalse(self.signup.deleted)
        self.assertEqual(self.signup.last_modified_by_id, self.user.pk)
        self.assertTrue(self.signup.last_modified_time > signup_last_modified_time)

        self.assertFalse(contact_person.deleted)
        self.assertFalse(protected_data.deleted)
        self.assertFalse(price_group.deleted)

        self.assertFalse(payment.deleted)
        self.assertEqual(payment.last_modified_by_id, self.user.pk)
        self.assertTrue(payment.last_modified_time > payment_last_modified_time)

        self.assertFalse(payment_refund.deleted)

        self.assertFalse(payment_cancellation.deleted)

    def test_price_groups(self):
        signup_group = SignUpGroupFactory(registration=self.signup.registration)

        self.signup.signup_group = signup_group
        self.signup.save(update_fields=["signup_group"])

        price_group = SignUpPriceGroupFactory(signup=self.signup)

        SignUpPriceGroupFactory(signup__registration=self.signup.registration)
        SignUpPriceGroupFactory(
            signup__registration=signup_group.registration,
            signup__signup_group=signup_group,
        )

        self.assertListEqual(self.signup.price_groups, [price_group])

    def test_price_groups_is_empty_list(self):
        self.assertEqual(len(self.signup.price_groups), 0)


class TestSignUpContactPerson(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contact_person = SignUpContactPersonFactory(signup=SignUpFactory())

    def test_cannot_save_without_signup_or_signup_group(self):
        self.contact_person.signup = None

        with self.assertRaises(ValidationError):
            self.contact_person.save()

    def test_cannot_save_with_both_signup_and_signup_group(self):
        self.contact_person.signup_group = SignUpGroupFactory()

        with self.assertRaises(ValidationError):
            self.contact_person.save()

    def test_get_service_language_pk(self):
        sv = Language.objects.create(
            name="Swedish",
            pk="sv",
        )
        self.contact_person.service_language = sv
        self.contact_person.save(update_fields=["service_language"])

        self.assertEqual(self.contact_person.get_service_language_pk(), "sv")

    def test_get_default_service_language_pk(self):
        self.contact_person.service_language = None
        self.contact_person.save(update_fields=["service_language"])

        self.assertEqual(self.contact_person.get_service_language_pk(), "fi")

    def test_signup_registration(self):
        self.assertEqual(
            self.contact_person.registration.pk,
            self.contact_person.signup.registration_id,
        )

    def test_signup_group_registration(self):
        self.contact_person.signup = None
        self.contact_person.signup_group = SignUpGroupFactory()
        self.contact_person.save(update_fields=["signup", "signup_group"])

        self.assertEqual(
            self.contact_person.registration.pk,
            self.contact_person.signup_group.registration_id,
        )

    def test_can_create_access_code(self):
        self.user = UserFactory(email="test@test.com")

        self.contact_person.email = "test2@test.com"
        self.contact_person.save(update_fields=["email"])
        self.assertNotEqual(self.contact_person.email, self.user.email)

        self.assertTrue(self.contact_person.can_create_access_code(self.user))

    def test_cannot_create_access_code_without_contact_person_email(self):
        self.user = UserFactory(email="test@test.com")

        # Email address is None.
        self.assertIsNone(self.contact_person.email)
        self.assertFalse(self.contact_person.can_create_access_code(self.user))

        # Email address is an empty string.
        self.contact_person.email = ""
        self.contact_person.save(update_fields=["email"])
        self.assertFalse(self.contact_person.can_create_access_code(self.user))

    def test_cannot_create_access_code_if_already_have_full_permissions(self):
        self.user = UserFactory(email="test@test.com")

        self.user.registration_admin_organizations.add(
            self.contact_person.signup.publisher
        )
        self.contact_person.email = self.user.email
        self.contact_person.save(update_fields=["email"])

        self.assertFalse(self.contact_person.can_create_access_code(self.user))

    def test_create_access_code(self):
        self.assertIsNone(self.contact_person.access_code)

        access_code = self.contact_person.create_access_code()
        self.assertTrue(isinstance(access_code, str))

        self.contact_person.refresh_from_db()
        self.assertIsNotNone(self.contact_person.access_code)
        self.assertTrue(self.contact_person.check_access_code(access_code))

    def test_check_access_code(self):
        access_code = self.contact_person.create_access_code()
        self.assertTrue(self.contact_person.check_access_code(access_code))

    def test_check_access_code_no_code_created(self):
        self.assertIsNone(self.contact_person.access_code)
        self.assertFalse(self.contact_person.check_access_code(str(uuid4())))

    def test_check_access_code_invalid_code_given(self):
        access_code = self.contact_person.create_access_code()

        # Create a unique wrong access code.
        while (wrong_access_code := str(uuid4())) == access_code:
            pass

        for access_code_arg in ["", None, "not-uuid4", wrong_access_code]:
            with self.subTest():
                self.assertFalse(self.contact_person.check_access_code(access_code_arg))

    def test_check_access_code_already_used(self):
        access_code = self.contact_person.create_access_code()

        self.contact_person.link_user(UserFactory())
        self.assertFalse(self.contact_person.check_access_code(access_code))

    def test_send_notification(self):
        self.contact_person.email = "test@test.dev"
        self.contact_person.save(update_fields=["email"])

        for notification_type in (
            SignUpNotificationType.EVENT_CANCELLATION,
            SignUpNotificationType.CANCELLATION,
            SignUpNotificationType.CONFIRMATION,
            SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST,
            SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT,
        ):
            with self.subTest():
                self.contact_person.send_notification(notification_type)

                self.assertEqual(len(mail.outbox), 1)
                self.assertEqual(mail.outbox[0].to[0], self.contact_person.email)

                mail.outbox.clear()

    def test_send_notification_with_access_code(self):
        self.contact_person.email = "test@test.dev"
        self.contact_person.save(update_fields=["email"])

        access_code = str(uuid4())

        for notification_type in (
            SignUpNotificationType.CONFIRMATION,
            SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST,
        ):
            with self.subTest():
                self.contact_person.send_notification(
                    notification_type, access_code=access_code
                )

                self.assertEqual(len(mail.outbox), 1)
                self.assertEqual(mail.outbox[0].to[0], self.contact_person.email)
                self.assertTrue(access_code in str(mail.outbox[0].alternatives[0]))

                mail.outbox.clear()

    def test_send_notification_unknown_notification_type(self):
        self.contact_person.email = "test@test.dev"
        self.contact_person.save(update_fields=["email"])

        with self.assertRaises(ValueError):
            self.contact_person.send_notification("does-not-exist")

        self.assertEqual(len(mail.outbox), 0)

    def test_to_web_store_order_json(self):
        self.contact_person.first_name = "Mickey"
        self.contact_person.last_name = "Mouse"
        self.contact_person.email = "mickey@test.com"
        self.contact_person.phone_number = "+3581111111111"
        self.contact_person.save(
            update_fields=["first_name", "last_name", "email", "phone_number"]
        )

        self.assertDictEqual(
            self.contact_person.to_web_store_order_json(),
            {
                "firstName": self.contact_person.first_name,
                "lastName": self.contact_person.last_name,
                "email": self.contact_person.email,
                "phone": self.contact_person.phone_number,
            },
        )

    def test_soft_delete(self):
        self.assertFalse(self.contact_person.deleted)

        self.contact_person.soft_delete()

        self.contact_person.refresh_from_db()
        self.assertTrue(self.contact_person.deleted)

    def test_undelete(self):
        self.contact_person.deleted = True
        self.contact_person.save(update_fields=["deleted"])
        self.assertTrue(self.contact_person.deleted)

        self.contact_person.undelete()

        self.contact_person.refresh_from_db()
        self.assertFalse(self.contact_person.deleted)


class TestRegistrationPriceGroup(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.registration_price_group = RegistrationPriceGroupFactory(price=Decimal("0"))

    def test_calculate_vat_and_price_without_vat(self):
        self.registration_price_group.price = Decimal("324")
        self.registration_price_group.vat_percentage = VatPercentage.VAT_25_5.value

        self.assertEqual(self.registration_price_group.price_without_vat, Decimal("0"))
        self.assertEqual(self.registration_price_group.vat, Decimal("0"))

        self.registration_price_group.calculate_vat_and_price_without_vat()

        self.assertEqual(
            self.registration_price_group.price_without_vat, Decimal("258.17")
        )
        self.assertEqual(self.registration_price_group.vat, Decimal("65.83"))


class TestSignUpPriceGroup(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.price_group = SignUpPriceGroupFactory()

    def test_to_web_store_order_json(self):
        product_mapping = RegistrationWebStoreProductMappingFactory(
            registration=self.price_group.signup.registration
        )

        price_net = str(
            strip_trailing_zeroes_from_decimal(self.price_group.price_without_vat)
        )
        price_vat = str(strip_trailing_zeroes_from_decimal(self.price_group.vat))
        price_total = str(strip_trailing_zeroes_from_decimal(self.price_group.price))

        self.assertDictEqual(
            self.price_group.to_web_store_order_json(),
            {
                "productId": product_mapping.external_product_id,
                "productName": self.price_group.description_en,
                "quantity": 1,
                "unit": "pcs",
                "rowPriceNet": price_net,
                "rowPriceVat": price_vat,
                "rowPriceTotal": price_total,
                "priceNet": price_net,
                "priceGross": price_total,
                "priceVat": price_vat,
                "vatPercentage": str(
                    strip_trailing_zeroes_from_decimal(self.price_group.vat_percentage)
                ),
                "meta": [
                    {
                        "key": web_store_price_group_meta_key,
                        "value": str(self.price_group.pk),
                        "visibleInCheckout": False,
                        "ordinal": "0",
                    }
                ],
            },
        )

    def test_soft_delete(self):
        self.assertFalse(self.price_group.deleted)

        self.price_group.soft_delete()

        self.price_group.refresh_from_db()
        self.assertTrue(self.price_group.deleted)

    def test_undelete(self):
        self.price_group.deleted = True
        self.price_group.save(update_fields=["deleted"])
        self.assertTrue(self.price_group.deleted)

        self.price_group.undelete()

        self.price_group.refresh_from_db()
        self.assertFalse(self.price_group.deleted)


class TestSignUpPayment(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.payment = SignUpPaymentFactory()

    def test_soft_delete(self):
        payment_refund = SignUpPaymentRefundFactory(
            payment=self.payment, signup=self.payment.signup
        )
        payment_cancellation = SignUpPaymentCancellationFactory(
            payment=self.payment, signup=self.payment.signup
        )

        self.assertFalse(self.payment.deleted)
        self.assertFalse(payment_refund.deleted)
        self.assertFalse(payment_cancellation.deleted)

        self.payment.soft_delete()

        self.payment.refresh_from_db()
        payment_refund.refresh_from_db()
        payment_cancellation.refresh_from_db()

        self.assertTrue(self.payment.deleted)
        self.assertTrue(payment_refund.deleted)
        self.assertTrue(payment_cancellation.deleted)

    def test_undelete(self):
        payment_refund = SignUpPaymentRefundFactory(
            payment=self.payment, signup=self.payment.signup
        )
        payment_cancellation = SignUpPaymentCancellationFactory(
            payment=self.payment, signup=self.payment.signup
        )
        self.payment.soft_delete()

        self.payment.refresh_from_db()
        payment_refund.refresh_from_db()
        payment_cancellation.refresh_from_db()

        self.assertTrue(self.payment.deleted)
        self.assertTrue(payment_refund.deleted)
        self.assertTrue(payment_cancellation.deleted)

        self.payment.undelete()

        self.payment.refresh_from_db()
        payment_refund.refresh_from_db()
        payment_cancellation.refresh_from_db()

        self.assertFalse(self.payment.deleted)
        self.assertFalse(payment_refund.deleted)
        self.assertFalse(payment_cancellation.deleted)


class TestWebStoreMerchant(TestCase):
    @classmethod
    def setUpTestData(cls):
        with cls.settings(cls, WEB_STORE_INTEGRATION_ENABLED=False):
            cls.merchant = WebStoreMerchantFactory()

    def test_delete_not_allowed(self):
        with self.assertRaises(ValidationError) as exc:
            self.merchant.delete()
        self.assertEqual(exc.exception.messages[0], "Cannot delete a Talpa merchant.")

        self.assertEqual(WebStoreMerchant.objects.count(), 1)

    def test_force_delete(self):
        self.merchant.delete(force_delete=True)

        self.assertEqual(WebStoreMerchant.objects.count(), 0)

    def test_to_web_store_merchant_json(self):
        self.assertDictEqual(
            {
                "merchantName": self.merchant.name,
                "merchantStreet": self.merchant.street_address,
                "merchantZip": self.merchant.zipcode,
                "merchantCity": self.merchant.city,
                "merchantEmail": self.merchant.email,
                "merchantPhone": self.merchant.phone_number,
                "merchantUrl": self.merchant.url,
                "merchantTermsOfServiceUrl": self.merchant.terms_of_service_url,
                "merchantBusinessId": self.merchant.business_id,
                "merchantPaytrailMerchantId": self.merchant.paytrail_merchant_id,
                "merchantShopId": self.merchant.paytrail_merchant_id,
            },
            self.merchant.to_web_store_merchant_json(),
        )


class TestWebStoreAccount(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = WebStoreAccountFactory()

    def test_delete_not_allowed(self):
        with self.assertRaises(ValidationError) as exc:
            self.account.delete()
        self.assertEqual(exc.exception.messages[0], "Cannot delete a Talpa account.")

        self.assertEqual(WebStoreAccount.objects.count(), 1)

    def test_force_delete(self):
        self.account.delete(force_delete=True)

        self.assertEqual(WebStoreAccount.objects.count(), 0)
