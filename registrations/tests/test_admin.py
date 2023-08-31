from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import translation
from rest_framework import status

from registrations.admin import RegistrationAdmin
from registrations.models import Event, Registration, RegistrationUserAccess
from registrations.tests.factories import RegistrationFactory
from registrations.tests.utils import assert_invitation_email_is_sent

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
        self.client.force_login(self.admin)

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
                "_save": "Save",
            },
        )

        # Test that create_by values is set to current user
        registration = Registration.objects.get(event=event2)
        self.assertEqual(
            self.admin,
            registration.created_by,
        )

    def test_registration_user_accesses_cannot_have_duplicate_emails(self):
        with translation.override("en"):
            self.client.force_login(self.admin)

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
                    "_save": "Save",
                },
            )

            self.assertContains(
                response, "Please correct the duplicate data for email.", html=True
            )

    def test_send_invitation_email_when_adding_registration_user_access(self):
        with translation.override("fi"):
            self.client.force_login(self.admin)

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
                    "_save": "Save",
                },
            )

            assert response.status_code == status.HTTP_302_FOUND
            assert response.url == "/admin/registrations/registration/"
            # Assert that invitation is sent to registration user
            assert_invitation_email_is_sent(EMAIL, EVENT_NAME)

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
            self.client.force_login(self.admin)

            registration_user_access = RegistrationUserAccess.objects.create(
                registration=self.registration, email=EMAIL
            )
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
                    "_save": "Save",
                },
            )

            assert response.status_code == status.HTTP_302_FOUND
            assert response.url == "/admin/registrations/registration/"
            # Assert that invitation is sent to updated email
            assert_invitation_email_is_sent(EDITED_EMAIL, EVENT_NAME)
