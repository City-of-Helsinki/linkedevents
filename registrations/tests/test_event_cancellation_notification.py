from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import patch
from uuid import uuid4

import pytest
import requests_mock
from django.conf import settings
from django.core import mail
from django.utils import translation
from django.utils.timezone import localtime
from rest_framework import status
from rest_framework.test import APITestCase

from events.models import Event
from events.tests.conftest import TEXT_EN, TEXT_FI, TEXT_SV
from events.tests.factories import EventFactory, LanguageFactory, PlaceFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp, SignUpContactPerson, SignUpGroup, SignUpPayment
from registrations.notifications import (
    SignUpNotificationType,
    recurring_event_signup_email_texts,
    recurring_event_signup_notification_subjects,
    signup_email_texts,
    signup_notification_subjects,
)
from registrations.tests.factories import (
    RegistrationFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpPaymentFactory,
)
from web_store.tests.order.test_web_store_order_api_client import (
    DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE,
    DEFAULT_ORDER_ID,
)


@pytest.mark.usefixtures("make_complex_event_dict_class")
class EventCancellationNotificationAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        registration = RegistrationFactory(
            event__name_en=TEXT_EN,
            event__name_sv=TEXT_SV,
            event__name_fi=TEXT_FI,
            event__data_source__user_editable_resources=True,
        )

        cls.event = registration.event
        cls.event_detail_url = reverse("event-detail", kwargs={"pk": cls.event.pk})

        cls.languages = [
            LanguageFactory(id="fi", service_language=True),
            LanguageFactory(id="sv", service_language=True),
            LanguageFactory(id="en", service_language=True),
        ]

        place = PlaceFactory(
            data_source=cls.event.data_source, publisher=cls.event.publisher
        )
        cls.location_id = reverse("place-detail", kwargs={"pk": place.pk})

        cls.user = UserFactory()
        cls.user.admin_organizations.add(cls.event.publisher)

        cls._create_signups_and_contact_persons_for_registration(registration)

        signup_group = SignUpGroupFactory(registration=registration)
        SignUpContactPersonFactory(
            signup_group=signup_group,
            email="test-group@test.com",
            service_language=cls.languages[2],
        )
        SignUpFactory(registration=registration, signup_group=signup_group)
        SignUpFactory(registration=registration, signup_group=signup_group)

    def setUp(self):
        self.client.force_authenticate(self.user)

    def assertCancellationEmailsSent(self, contact_person_count):
        # Both event cancellation and signup cancellation emails will be sent
        # so two emails per each of the three contact persons.
        self.assertEqual(len(mail.outbox), contact_person_count * 2)

        notification_subject = signup_notification_subjects[
            SignUpNotificationType.EVENT_CANCELLATION
        ]
        notification_texts = signup_email_texts[
            SignUpNotificationType.EVENT_CANCELLATION
        ]

        contact_persons = SignUpContactPerson.objects.all().order_by("-pk")
        for index, contact_person in enumerate(contact_persons):
            self.assertEqual(mail.outbox[index].to[0], contact_person.email)

            with translation.override(contact_person.service_language.pk):
                self.assertEqual(
                    mail.outbox[index].subject,
                    notification_subject % {"event_name": self.event.name},
                )

                html_message = str(mail.outbox[index].alternatives[0])
                self.assertTrue(
                    notification_texts["heading"] % {"event_name": self.event.name}
                    in html_message
                )
                self.assertTrue(str(notification_texts["text"]) in html_message)

    def assertCancellationEmailsSentForRecurringEvent(self, contact_person_count):
        # Both event cancellation and signup cancellation emails will be sent
        # so two emails per each of the three contact persons.
        self.assertEqual(len(mail.outbox), contact_person_count * 2)

        notification_subject = recurring_event_signup_notification_subjects[
            SignUpNotificationType.EVENT_CANCELLATION
        ]
        notification_texts = recurring_event_signup_email_texts[
            SignUpNotificationType.EVENT_CANCELLATION
        ]

        contact_persons = SignUpContactPerson.objects.all().order_by("-pk")
        for index, contact_person in enumerate(contact_persons):
            self.assertEqual(mail.outbox[index].to[0], contact_person.email)

            with translation.override(contact_person.service_language.pk):
                self.assertEqual(
                    mail.outbox[index].subject,
                    notification_subject % {"event_name": self.event.name},
                )

                html_message = str(mail.outbox[index].alternatives[0])
                self.assertTrue(
                    notification_texts["heading"]
                    % {
                        "event_name": self.event.name,
                        "event_period": self.event.get_start_and_end_time_display(
                            lang=contact_person.service_language.pk, date_only=True
                        ),
                    }
                    in html_message
                )
                self.assertTrue(str(notification_texts["text"]) in html_message)

    def assertCancellationEmailsSentForRecurringSubEvent(self, contact_person_count):
        # Only sub-event cancellation emails are sent. Signups related to the recurring super-event
        # are not cancelled so no additional emails are sent about them.
        self.assertEqual(len(mail.outbox), contact_person_count)

        notification_subject = signup_notification_subjects[
            SignUpNotificationType.EVENT_CANCELLATION
        ]
        notification_texts = signup_email_texts[
            SignUpNotificationType.EVENT_CANCELLATION
        ]

        contact_persons = SignUpContactPerson.objects.filter().order_by("-pk")
        for index, contact_person in enumerate(contact_persons):
            self.assertEqual(mail.outbox[index].to[0], contact_person.email)

            with translation.override(contact_person.service_language.pk):
                self.assertEqual(
                    mail.outbox[index].subject,
                    notification_subject % {"event_name": self.event.name},
                )

                html_message = str(mail.outbox[index].alternatives[0])
                self.assertTrue(
                    notification_texts["sub_event_cancellation"]["heading"]
                    % {
                        "event_name": self.event.name,
                        "event_period": self.event.get_start_and_end_time_display(
                            lang=contact_person.service_language.pk, date_only=True
                        ),
                    }
                    in html_message
                )
                self.assertTrue(str(notification_texts["text"]) in html_message)

    @classmethod
    def _create_signups_and_contact_persons_for_registration(
        cls, registration, number_of_signups=2
    ):
        assert number_of_signups <= len(cls.languages)

        for idx in range(0, number_of_signups):
            signup = SignUpFactory(registration=registration)
            SignUpContactPersonFactory(
                signup=signup,
                email=f"test-signup{idx}@test.com",
                service_language=cls.languages[idx],
            )

    @staticmethod
    def _create_signup_payments(payments_kwargs: Optional[list[dict]] = None):
        if payments_kwargs:
            for payment_kwargs in payments_kwargs:
                SignUpPaymentFactory(**payment_kwargs)
        else:
            signup_group = SignUpGroup.objects.first()
            SignUpPaymentFactory(
                signup=None,
                signup_group=signup_group,
                external_order_id=DEFAULT_ORDER_ID,
                status=SignUpPayment.PaymentStatus.PAID,
            )

            signup_without_group = SignUp.objects.filter(
                registration_id=signup_group.registration_id,
                signup_group_id__isnull=True,
            ).first()
            SignUpPaymentFactory(
                signup=signup_without_group,
                external_order_id=DEFAULT_ORDER_ID,
                status=SignUpPayment.PaymentStatus.PAID,
            )

    @staticmethod
    def _create_sub_event(
        event,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ):
        sub_event = EventFactory(
            data_source=event.data_source,
            publisher=event.publisher,
            super_event=event,
            start_time=start_time or event.start_time,
            end_time=end_time or event.start_time + timedelta(hours=1),
        )
        sub_event_detail_url = reverse("event-detail", kwargs={"pk": sub_event.pk})

        return sub_event, sub_event_detail_url

    @staticmethod
    def _make_super_event(
        event,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ):
        event.super_event_type = Event.SuperEventType.RECURRING
        event.start_time = start_time or localtime()
        event.end_time = end_time or event.start_time + timedelta(days=30)
        event.save(update_fields=["super_event_type", "start_time", "end_time"])

    def test_event_put_signups_cancelled_and_cancellation_emails_sent_to_contact_persons(
        self,
    ):
        contact_person_count = SignUpContactPerson.objects.count()
        self.assertEqual(contact_person_count, 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)

        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)

        complex_event_dict = self.make_complex_event_dict(
            self.event.data_source,
            self.event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict["event_status"] = "EventCancelled"

        response = self.client.put(
            self.event_detail_url,
            complex_event_dict,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event.refresh_from_db()
        self.assertEqual(self.event.event_status, Event.Status.CANCELLED)

        self.assertEqual(SignUpGroup.objects.count(), 0)
        self.assertEqual(SignUp.objects.count(), 0)

        self.assertCancellationEmailsSent(contact_person_count)

    def test_cannot_cancel_event_with_paid_signups(self):
        signup_group = SignUpGroup.objects.first()
        self._create_signup_payments(
            [
                {
                    "signup": None,
                    "signup_group": signup_group,
                    "external_order_id": DEFAULT_ORDER_ID,
                },
                {
                    "signup": SignUp.objects.filter(
                        registration_id=signup_group.registration_id,
                        signup_group_id__isnull=True,
                    ).first(),
                    "external_order_id": DEFAULT_ORDER_ID,
                },
            ]
        )

        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)
        self.assertEqual(SignUpPayment.objects.count(), 2)

        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)

        complex_event_dict = self.make_complex_event_dict(
            self.event.data_source,
            self.event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict["event_status"] = "EventCancelled"

        response = self.client.put(
            self.event_detail_url,
            complex_event_dict,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data[0],
            (
                "Trying to cancel an event with paid signups. "
                "Please cancel the signups first before cancelling the event."
            ),
        )

        self.event.refresh_from_db()
        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)

        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)
        self.assertEqual(SignUpPayment.objects.count(), 2)

        self.assertEqual(len(mail.outbox), 0)

    def test_event_bulk_update_cannot_refund_paid_signups(self):
        registration2 = RegistrationFactory(event__publisher=self.event.publisher)
        event2 = registration2.event

        signup_group2 = SignUpGroupFactory(registration=registration2)
        SignUpFactory(signup_group=signup_group2, registration=registration2)
        SignUpContactPersonFactory(
            signup_group=signup_group2,
            email="test-group2@test.com",
            service_language=self.languages[2],
        )

        signup6 = SignUpFactory(registration=registration2)
        SignUpContactPersonFactory(
            signup=signup6,
            email="test-signup6@test.com",
            service_language=self.languages[2],
        )

        external_order_id2 = str(uuid4())

        self._create_signup_payments()
        self._create_signup_payments(
            [
                {
                    "signup": None,
                    "signup_group": signup_group2,
                    "external_order_id": external_order_id2,
                    "status": SignUpPayment.PaymentStatus.PAID,
                },
                {
                    "signup": signup6,
                    "external_order_id": external_order_id2,
                    "status": SignUpPayment.PaymentStatus.PAID,
                },
            ]
        )

        contact_person_count = SignUpContactPerson.objects.count()
        self.assertEqual(contact_person_count, 5)
        self.assertEqual(SignUpGroup.objects.count(), 2)
        self.assertEqual(SignUp.objects.count(), 6)
        self.assertEqual(SignUpPayment.objects.count(), 4)

        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)
        self.assertNotEqual(event2.event_status, Event.Status.CANCELLED)

        complex_event_dict = self.make_complex_event_dict(
            self.event.data_source,
            self.event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict["id"] = self.event.pk
        complex_event_dict["event_status"] = "EventCancelled"

        complex_event_dict2 = self.make_complex_event_dict(
            event2.data_source,
            event2.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict2["id"] = event2.pk
        complex_event_dict2["event_status"] = "EventCancelled"

        response = self.client.put(
            reverse("event-list"),
            [complex_event_dict, complex_event_dict2],
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data[0],
            (
                "Trying to cancel an event with paid signups. "
                "Please cancel the signups first before cancelling the event."
            ),
        )

        self.event.refresh_from_db()
        event2.refresh_from_db()

        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)
        self.assertNotEqual(event2.event_status, Event.Status.CANCELLED)

        self.assertEqual(SignUpContactPerson.objects.count(), 5)
        self.assertEqual(SignUpGroup.objects.count(), 2)
        self.assertEqual(SignUp.objects.count(), 6)
        self.assertEqual(SignUpPayment.objects.count(), 4)

        self.assertEqual(len(mail.outbox), 0)

    def test_event_bulk_update_cannot_cancel_paid_signups(self):
        registration2 = RegistrationFactory(event__publisher=self.event.publisher)
        event2 = registration2.event

        signup_group = SignUpGroup.objects.first()

        signup_group2 = SignUpGroupFactory(registration=registration2)
        SignUpFactory(signup_group=signup_group2, registration=registration2)
        SignUpContactPersonFactory(
            signup_group=signup_group2,
            email="test-group2@test.com",
            service_language=self.languages[2],
        )

        signup6 = SignUpFactory(registration=registration2)
        SignUpContactPersonFactory(
            signup=signup6,
            email="test-signup6@test.com",
            service_language=self.languages[2],
        )

        external_order_id2 = str(uuid4())

        self._create_signup_payments(
            [
                {
                    "signup": None,
                    "signup_group": signup_group,
                    "external_order_id": DEFAULT_ORDER_ID,
                },
                {
                    "signup": SignUp.objects.filter(
                        registration_id=signup_group.registration_id,
                        signup_group_id__isnull=True,
                    ).first(),
                    "external_order_id": DEFAULT_ORDER_ID,
                },
                {
                    "signup": None,
                    "signup_group": signup_group2,
                    "external_order_id": external_order_id2,
                },
                {
                    "signup": signup6,
                    "external_order_id": external_order_id2,
                },
            ]
        )

        contact_person_count = SignUpContactPerson.objects.count()
        self.assertEqual(contact_person_count, 5)
        self.assertEqual(SignUpGroup.objects.count(), 2)
        self.assertEqual(SignUp.objects.count(), 6)
        self.assertEqual(SignUpPayment.objects.count(), 4)

        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)
        self.assertNotEqual(event2.event_status, Event.Status.CANCELLED)

        complex_event_dict = self.make_complex_event_dict(
            self.event.data_source,
            self.event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict["id"] = self.event.pk
        complex_event_dict["event_status"] = "EventCancelled"

        complex_event_dict2 = self.make_complex_event_dict(
            event2.data_source,
            event2.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict2["id"] = event2.pk
        complex_event_dict2["event_status"] = "EventCancelled"

        response = self.client.put(
            reverse("event-list"),
            [complex_event_dict, complex_event_dict2],
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data[0],
            (
                "Trying to cancel an event with paid signups. "
                "Please cancel the signups first before cancelling the event."
            ),
        )

        self.event.refresh_from_db()
        event2.refresh_from_db()

        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)
        self.assertNotEqual(event2.event_status, Event.Status.CANCELLED)

        self.assertEqual(SignUpContactPerson.objects.count(), 5)
        self.assertEqual(SignUpGroup.objects.count(), 2)
        self.assertEqual(SignUp.objects.count(), 6)
        self.assertEqual(SignUpPayment.objects.count(), 4)

        self.assertEqual(len(mail.outbox), 0)

    def test_event_put_signups_cancelled_and_cancellation_emails_sent_for_recurring_event(
        self,
    ):
        self._make_super_event(self.event)

        contact_person_count = SignUpContactPerson.objects.count()
        self.assertEqual(contact_person_count, 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)

        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)

        complex_event_dict = self.make_complex_event_dict(
            self.event.data_source,
            self.event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict.update(
            {
                "event_status": "EventCancelled",
                "start_time": self.event.start_time,
                "end_time": self.event.end_time,
            }
        )

        response = self.client.put(
            self.event_detail_url,
            complex_event_dict,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event.refresh_from_db()
        self.assertEqual(self.event.event_status, Event.Status.CANCELLED)

        self.assertEqual(SignUpContactPerson.objects.count(), 0)
        self.assertEqual(SignUpGroup.objects.count(), 0)
        self.assertEqual(SignUp.objects.count(), 0)

        self.assertCancellationEmailsSentForRecurringEvent(contact_person_count)

    def test_cannot_cancel_recurring_event_with_paid_signups(
        self,
    ):
        self._create_signup_payments()
        self._make_super_event(self.event)

        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)
        self.assertEqual(SignUpPayment.objects.count(), 2)

        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)

        complex_event_dict = self.make_complex_event_dict(
            self.event.data_source,
            self.event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict.update(
            {
                "event_status": "EventCancelled",
                "start_time": self.event.start_time,
                "end_time": self.event.end_time,
            }
        )

        response = self.client.put(
            self.event_detail_url,
            complex_event_dict,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data[0],
            (
                "Trying to cancel an event with paid signups. "
                "Please cancel the signups first before cancelling the event."
            ),
        )

        self.event.refresh_from_db()
        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)

        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)
        self.assertEqual(SignUpPayment.objects.count(), 2)

        self.assertEqual(len(mail.outbox), 0)

    def test_recurring_sub_event_put_cancellation_emails_sent_signups_not_cancelled_for_super_event(
        self,
    ):
        self._make_super_event(self.event)
        sub_event, sub_event_detail_url = self._create_sub_event(self.event)

        contact_person_count = SignUpContactPerson.objects.count()
        self.assertEqual(contact_person_count, 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)

        self.assertNotEqual(sub_event.event_status, Event.Status.CANCELLED)

        complex_event_dict = self.make_complex_event_dict(
            sub_event.data_source,
            sub_event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict.update(
            {
                "event_status": "EventCancelled",
                "start_time": sub_event.start_time,
                "end_time": sub_event.end_time,
            }
        )

        response = self.client.put(
            sub_event_detail_url,
            complex_event_dict,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event.refresh_from_db()
        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)

        sub_event.refresh_from_db()
        self.assertEqual(sub_event.event_status, Event.Status.CANCELLED)

        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)

        self.assertCancellationEmailsSentForRecurringSubEvent(contact_person_count)

    def test_recurring_sub_event_put_cancellation_emails_sent_payments_not_refunded_for_super_event(
        self,
    ):
        self._create_signup_payments()
        self._make_super_event(self.event)
        sub_event, sub_event_detail_url = self._create_sub_event(self.event)

        contact_person_count = SignUpContactPerson.objects.count()
        self.assertEqual(contact_person_count, 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)

        self.assertNotEqual(sub_event.event_status, Event.Status.CANCELLED)

        complex_event_dict = self.make_complex_event_dict(
            sub_event.data_source,
            sub_event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict.update(
            {
                "event_status": "EventCancelled",
                "start_time": sub_event.start_time,
                "end_time": sub_event.end_time,
            }
        )

        with requests_mock.Mocker() as req_mock:
            req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}order/refund/instant",
                json=DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE,
            )

            response = self.client.put(
                sub_event_detail_url,
                complex_event_dict,
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            self.assertEqual(req_mock.call_count, 0)

        self.event.refresh_from_db()
        self.assertNotEqual(self.event.event_status, Event.Status.CANCELLED)

        sub_event.refresh_from_db()
        self.assertEqual(sub_event.event_status, Event.Status.CANCELLED)

        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)

        self.assertCancellationEmailsSentForRecurringSubEvent(contact_person_count)

    def test_event_put_signups_not_cancelled_and_cancellation_emails_not_sent_if_cancelled_again(
        self,
    ):
        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)

        Event.objects.filter(pk=self.event.pk).update(
            event_status=Event.Status.CANCELLED
        )

        complex_event_dict = self.make_complex_event_dict(
            self.event.data_source,
            self.event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict["event_status"] = "EventCancelled"

        response = self.client.put(
            self.event_detail_url,
            complex_event_dict,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event.refresh_from_db()
        self.assertEqual(self.event.event_status, Event.Status.CANCELLED)

        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)

        self.assertEqual(len(mail.outbox), 0)

    def test_event_put_signups_not_cancelled_and_payments_not_refunded_if_cancelled_again(
        self,
    ):
        self._create_signup_payments()

        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)
        self.assertEqual(SignUpPayment.objects.count(), 2)

        Event.objects.filter(pk=self.event.pk).update(
            event_status=Event.Status.CANCELLED
        )

        complex_event_dict = self.make_complex_event_dict(
            self.event.data_source,
            self.event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict["event_status"] = "EventCancelled"

        with requests_mock.Mocker() as req_mock:
            req_mock.post(
                f"{settings.WEB_STORE_API_BASE_URL}order/refund/instant",
                json=DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE,
            )

            response = self.client.put(
                self.event_detail_url,
                complex_event_dict,
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            self.assertEqual(req_mock.call_count, 0)

        self.event.refresh_from_db()
        self.assertEqual(self.event.event_status, Event.Status.CANCELLED)

        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)
        self.assertEqual(SignUpPayment.objects.count(), 2)

        self.assertEqual(len(mail.outbox), 0)

    def test_event_put_cancellation_email_not_sent_to_contact_persons_if_transaction_rolled_back(
        self,
    ):
        self.assertEqual(SignUpContactPerson.objects.count(), 3)

        Event.objects.filter(pk=self.event.pk).update(
            event_status=Event.Status.CANCELLED
        )

        complex_event_dict = self.make_complex_event_dict(
            self.event.data_source,
            self.event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict["event_status"] = "EventCancelled"

        with patch(
            "django.db.models.signals.post_save.send"
        ) as mocked_post_save_signal:
            mocked_post_save_signal.side_effect = Exception

            with self.assertRaises(Exception):
                self.client.put(
                    self.event_detail_url,
                    complex_event_dict,
                    format="json",
                )

        self.assertEqual(len(mail.outbox), 0)

    def test_event_put_cancellation_email_not_sent_to_soft_deleted_contact_persons(
        self,
    ):
        for signup_group in SignUpGroup.objects.all():
            signup_group.soft_delete()

        for signup in SignUp.objects.all():
            signup.soft_delete()

        self.assertEqual(SignUpContactPerson.objects.count(), 0)
        self.assertEqual(SignUpContactPerson.all_objects.count(), 3)

        complex_event_dict = self.make_complex_event_dict(
            self.event.data_source,
            self.event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict["event_status"] = "EventCancelled"

        response = self.client.put(
            self.event_detail_url,
            complex_event_dict,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event.refresh_from_db()
        self.assertEqual(self.event.event_status, Event.Status.CANCELLED)

        self.assertEqual(len(mail.outbox), 0)

    def test_event_post_cancellation_email_not_sent_to_contact_persons(self):
        self.assertEqual(SignUpContactPerson.objects.count(), 3)

        self.assertEqual(Event.objects.count(), 1)

        complex_event_dict = self.make_complex_event_dict(
            self.event.data_source,
            self.event.publisher,
            self.location_id,
            self.languages,
        )
        complex_event_dict["event_status"] = "EventCancelled"
        del complex_event_dict["data_source"]

        events_url = reverse("event-list")
        response = self.client.post(
            events_url,
            complex_event_dict,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(Event.objects.count(), 2)

        self.assertEqual(len(mail.outbox), 0)

    def test_event_get_cancellation_email_not_sent_to_contact_persons(self):
        self.assertEqual(SignUpContactPerson.objects.count(), 3)

        response = self.client.get(
            self.event_detail_url,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(mail.outbox), 0)

    def test_event_delete_signups_cancelled_and_cancellation_emails_sent_to_contact_persons(
        self,
    ):
        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)

        response = self.client.delete(
            self.event_detail_url,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(SignUpContactPerson.objects.count(), 0)
        self.assertEqual(SignUpGroup.objects.count(), 0)
        self.assertEqual(SignUp.objects.count(), 0)

        # Event cancellation notifications + signup cancellation notifications
        # => 3 people * 2 notifications = 6 notifications.
        self.assertEqual(len(mail.outbox), 6)

    def test_cannot_delete_event_with_paid_signups(self):
        signup_group = SignUpGroup.objects.first()
        self._create_signup_payments(
            [
                {
                    "signup": None,
                    "signup_group": signup_group,
                    "external_order_id": DEFAULT_ORDER_ID,
                },
                {
                    "signup": SignUp.objects.filter(
                        registration_id=signup_group.registration_id,
                        signup_group_id__isnull=True,
                    ).first(),
                    "external_order_id": DEFAULT_ORDER_ID,
                },
            ]
        )

        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)
        self.assertEqual(SignUpPayment.objects.count(), 2)

        response = self.client.delete(
            self.event_detail_url,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data[0],
            (
                "Trying to cancel an event with paid signups. "
                "Please cancel the signups first before cancelling the event."
            ),
        )

        self.assertEqual(SignUpContactPerson.objects.count(), 3)
        self.assertEqual(SignUpGroup.objects.count(), 1)
        self.assertEqual(SignUp.objects.count(), 4)
        self.assertEqual(SignUpPayment.objects.count(), 2)

        self.assertEqual(len(mail.outbox), 0)
