from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import translation

from registrations.admin import RegistrationAdmin
from registrations.models import Event, Registration, RegistrationUser
from registrations.tests.factories import RegistrationFactory
from registrations.tests.test_registration_user_invitation import (
    assert_invitation_email_is_sent,
)

email = "user@email.com"
edited_email = "user_edited@email.com"
event_name = "Foo"


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
                "registration_users-TOTAL_FORMS": 1,
                "registration_users-INITIAL_FORMS": 0,
                "_save": "Save",
            },
        )

        # Test that create_by values is set to current user
        registration = Registration.objects.get(event=event2)
        self.assertEqual(
            self.admin,
            registration.created_by,
        )

    def test_registration_users_cannot_have_duplicate_emails(self):
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
                    "registration_users-TOTAL_FORMS": 2,
                    "registration_users-INITIAL_FORMS": 0,
                    "registration_users-0-email": email,
                    "registration_users-1-email": email,
                    "_save": "Save",
                },
            )

            self.assertContains(
                response, "Please correct the duplicate data for email.", html=True
            )

    def test_send_invitation_email_when_adding_registration_user(self):
        self.client.force_login(self.admin)

        # Create event for new registration
        data_source = self.registration.event.data_source
        publisher = self.registration.event.publisher
        event2 = Event.objects.create(
            id="event-2", data_source=data_source, name=event_name, publisher=publisher
        )

        # Create new registration
        self.client.post(
            "/admin/registrations/registration/add/",
            {
                "event": event2.id,
                "registration_users-TOTAL_FORMS": 1,
                "registration_users-INITIAL_FORMS": 0,
                "registration_users-0-email": email,
                "_save": "Save",
            },
        )

        # Assert that invitation is sent to registration user
        assert_invitation_email_is_sent(email, event_name)

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

    def test_send_invitation_email_when_registration_user_is_updated(self):
        self.client.force_login(self.admin)

        registration_user = RegistrationUser.objects.create(
            registration=self.registration, email=email
        )
        self.registration.event.name = event_name
        self.registration.event.save()

        # Update registration
        self.client.post(
            f"/admin/registrations/registration/{self.registration.id}/change/",
            {
                "event": self.registration.event.id,
                "registration_users-TOTAL_FORMS": 2,
                "registration_users-INITIAL_FORMS": 1,
                "registration_users-0-email": edited_email,
                "registration_users-0-id": registration_user.id,
                "registration_users-0-registration": self.registration.id,
                "_save": "Save",
            },
        )

        # Assert that invitation is sent to updated email
        assert_invitation_email_is_sent(edited_email, event_name)
