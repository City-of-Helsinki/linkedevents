from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
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
from registrations.models import SignUp, SignUpContactPerson, SignUpGroup
from registrations.notifications import (
    recurring_event_signup_email_texts,
    recurring_event_signup_notification_subjects,
    signup_email_texts,
    signup_notification_subjects,
    SignUpNotificationType,
)
from registrations.tests.factories import (
    RegistrationFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
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

    def test_event_put_cancellation_email_sent_to_contact_persons(self):
        contact_person_count = SignUpContactPerson.objects.count()
        self.assertEqual(contact_person_count, 3)

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

        self.assertEqual(len(mail.outbox), contact_person_count)

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

    def test_event_put_cancellation_email_sent_to_contact_persons_for_recurring_event(
        self,
    ):
        self.event.super_event_type = Event.SuperEventType.RECURRING
        self.event.start_time = localtime()
        self.event.end_time = self.event.start_time + timedelta(days=30)
        self.event.save(update_fields=["super_event_type", "start_time", "end_time"])

        contact_person_count = SignUpContactPerson.objects.count()
        self.assertEqual(contact_person_count, 3)

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

        self.assertEqual(len(mail.outbox), contact_person_count)

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

    def test_recurring_sub_event_put_cancellation_email_sent_to_contact_persons_of_super_event(
        self,
    ):
        self.event.super_event_type = Event.SuperEventType.RECURRING
        self.event.start_time = localtime()
        self.event.end_time = self.event.start_time + timedelta(days=30)
        self.event.save(update_fields=["super_event_type", "start_time", "end_time"])

        sub_event = EventFactory(
            data_source=self.event.data_source,
            publisher=self.event.publisher,
            super_event=self.event,
            start_time=self.event.start_time,
            end_time=self.event.start_time + timedelta(hours=1),
        )
        sub_event_detail_url = reverse("event-detail", kwargs={"pk": sub_event.pk})

        contact_person_count = SignUpContactPerson.objects.count()
        self.assertEqual(contact_person_count, 3)

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

    def test_event_put_cancellation_email_not_sent_to_contact_persons_if_cancelled_again(
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

        response = self.client.put(
            self.event_detail_url,
            complex_event_dict,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event.refresh_from_db()
        self.assertEqual(self.event.event_status, Event.Status.CANCELLED)

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

    def test_event_delete_cancellation_email_not_sent_to_contact_persons(self):
        self.assertEqual(SignUpContactPerson.objects.count(), 3)

        response = self.client.delete(
            self.event_detail_url,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(len(mail.outbox), 0)
