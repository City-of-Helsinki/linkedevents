from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from django_orghierarchy.models import Organization

from helevents.models import User, UserModelPermissionMixin
from registrations.models import RegistrationUserAccess
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationUserAccessFactory,
)
from registrations.tests.test_registration_post import hel_email

from ..models import DataSource, Event, PublicationStatus
from .factories import EventFactory, OrganizationFactory


class TestUserModelPermissionMixin(TestCase):
    def setUp(self):
        self.instance = UserModelPermissionMixin()

        self.data_source = DataSource.objects.create(
            id="ds",
            name="data-source",
            api_key="test_api_key",
            user_editable_resources=True,
        )
        self.org = Organization.objects.create(
            name="org",
            origin_id="org",
            data_source=self.data_source,
        )

    def test_is_admin(self):
        self.assertRaises(
            NotImplementedError,
            self.instance.is_admin_of,
            self.org,
        )

    def test_is_regular_user(self):
        self.assertRaises(
            NotImplementedError,
            self.instance.is_regular_user_of,
            self.org,
        )


@pytest.mark.parametrize(
    "membership_status, expected_public, expected_draft",
    [
        ("admin", True, True),
        ("regular", False, True),
        ("external", False, True),
    ],
)
@pytest.mark.django_db
def test_can_edit_event(membership_status, expected_public, expected_draft):
    instance = UserModelPermissionMixin()
    if membership_status == "external":
        org = None
    else:
        org = OrganizationFactory()

    with (
        patch.object(
            UserModelPermissionMixin,
            "is_admin_of",
            return_value=membership_status == "admin",
        ),
        patch.object(
            UserModelPermissionMixin,
            "is_regular_user_of",
            return_value=membership_status == "regular",
        ),
        patch.object(
            UserModelPermissionMixin,
            "is_external",
            return_value=membership_status == "external",
        ),
    ):
        assert (
            instance.can_edit_event(org, PublicationStatus.PUBLIC, instance)
            is expected_public
        )
        assert (
            instance.can_edit_event(org, PublicationStatus.DRAFT, instance)
            is expected_draft
        )


@pytest.mark.parametrize(
    "is_admin,is_registration_admin,is_financial_admin,is_regular_user,expected",
    [
        (True, True, True, True, False),
        (True, False, True, True, False),
        (True, False, False, False, False),
        (False, False, False, True, False),
        (True, True, False, False, False),
        (False, True, True, True, False),
        (False, True, False, False, False),
        (False, False, True, False, False),
        (False, False, False, False, True),
    ],
)
@pytest.mark.django_db
def test_user_is_external_based_on_group_membership(
    is_admin, is_registration_admin, is_financial_admin, is_regular_user, expected
):
    with (
        patch.object(
            User, "organization_memberships", new_callable=MagicMock
        ) as organization_memberships,
        patch.object(
            User, "admin_organizations", new_callable=MagicMock
        ) as admin_organizations,
        patch.object(
            User, "registration_admin_organizations", new_callable=MagicMock
        ) as registration_admin_organizations,
        patch.object(
            User, "financial_admin_organizations", new_callable=MagicMock
        ) as financial_admin_organizations,
    ):
        organization_memberships.exists.return_value = is_regular_user
        admin_organizations.exists.return_value = is_admin
        registration_admin_organizations.exists.return_value = is_registration_admin
        financial_admin_organizations.exists.return_value = is_financial_admin

        assert User().is_external is expected


class TestUserModelPermissions(TestCase):
    def setUp(self):
        self.instance = User.objects.create()

        self.data_source = DataSource.objects.create(
            id="ds",
            name="data-source",
            api_key="test_api_key",
            user_editable_resources=True,
        )
        self.org = Organization.objects.create(
            name="org",
            origin_id="org",
            data_source=self.data_source,
        )
        self.org2 = Organization.objects.create(
            name="org2", origin_id="org2", data_source=self.data_source, parent=self.org
        )

    def test_get_editable_events(self):
        # this test requires the whole User model, as admin organizations are dependent on org hierarchy
        event_1 = Event.objects.create(
            id="event-1",
            name="event-1",
            data_source=self.data_source,
            publisher=self.org,
            publication_status=PublicationStatus.PUBLIC,
        )
        event_2 = Event.objects.create(
            id="event-2",
            name="event-2",
            data_source=self.data_source,
            publisher=self.org,
            publication_status=PublicationStatus.DRAFT,
        )

        # admins should be allowed to see and edit suborg events
        event_3 = Event.objects.create(
            id="event-3",
            name="event-3",
            data_source=self.data_source,
            publisher=self.org2,
            publication_status=PublicationStatus.DRAFT,
        )

        total_qs = Event.objects.all()
        # test for admin user
        # magicmock cannot be used for object properties
        self.instance.admin_organizations.add(self.org)
        qs = self.instance.get_editable_events(total_qs)
        self.assertQuerySetEqual(
            qs,
            [repr(event_1), repr(event_2), repr(event_3)],
            ordered=False,
            transform=repr,
        )

        # test for regular user
        self.instance.admin_organizations.remove(self.org)
        self.instance.organization_memberships.add(self.org)
        qs = self.instance.get_editable_events(total_qs)
        self.assertQuerySetEqual(qs, [repr(event_2)], transform=repr)

        # test for other users
        self.instance.organization_memberships.remove(self.org)
        qs = self.instance.get_editable_events(total_qs)
        self.assertQuerySetEqual(qs, [], transform=repr)

    def test_admin_get_editable_events_for_registration(self):
        # this test requires the whole User model, as admin organizations are dependent on org hierarchy
        event_1 = EventFactory(
            id="event-1",
            name="event-1",
            data_source=self.data_source,
            publisher=self.org,
            publication_status=PublicationStatus.PUBLIC,
        )
        event_2 = EventFactory(
            id="event-2",
            name="event-2",
            data_source=self.data_source,
            publisher=self.org,
            publication_status=PublicationStatus.PUBLIC,
        )

        # admins should be allowed to see and edit suborg events
        event_3 = EventFactory(
            id="event-3",
            name="event-3",
            data_source=self.data_source,
            publisher=self.org2,
            publication_status=PublicationStatus.DRAFT,
        )

        total_qs = Event.objects.all()
        # test for registration admin user
        self.instance.registration_admin_organizations.add(self.org)
        qs = self.instance.get_editable_events_for_registration(total_qs)
        self.assertQuerySetEqual(
            qs, [repr(event_1), repr(event_2), repr(event_3)], transform=repr
        )

        # test for admin user
        self.instance.registration_admin_organizations.remove(self.org)
        self.instance.admin_organizations.add(self.org)
        qs = self.instance.get_editable_events_for_registration(total_qs)
        self.assertQuerySetEqual(
            qs, [repr(event_1), repr(event_2), repr(event_3)], transform=repr
        )

        # test for other users
        self.instance.admin_organizations.remove(self.org)
        qs = self.instance.get_editable_events_for_registration(total_qs)
        self.assertQuerySetEqual(qs, [], transform=repr)

    def test_substitute_user_get_editable_events_for_registration(self):
        event_1 = EventFactory(
            id="event-1",
            name="event-1",
            data_source=self.data_source,
            publisher=self.org,
            publication_status=PublicationStatus.PUBLIC,
        )
        RegistrationFactory(event=event_1)

        event_2 = EventFactory(
            id="event-2",
            name="event-2",
            data_source=self.data_source,
            publisher=self.org,
            publication_status=PublicationStatus.PUBLIC,
        )
        RegistrationFactory(event=event_2)

        event_3 = EventFactory(
            id="event-3",
            name="event-3",
            data_source=self.data_source,
            publisher=self.org2,
            publication_status=PublicationStatus.DRAFT,
        )
        RegistrationFactory(event=event_3)

        total_qs = Event.objects.all()

        # test for substitute user
        self.instance.email = hel_email
        self.instance.save(update_fields=["email"])
        RegistrationUserAccessFactory(
            registration=event_1.registration,
            email=hel_email,
            is_substitute_user=True,
        )
        RegistrationUserAccessFactory(
            registration=event_2.registration,
            email=hel_email,
            is_substitute_user=True,
        )
        RegistrationUserAccessFactory(
            registration=event_3.registration,
            email=hel_email,
            is_substitute_user=True,
        )
        qs = self.instance.get_editable_events_for_registration(total_qs)
        self.assertQuerySetEqual(
            qs, [repr(event_1), repr(event_2), repr(event_3)], transform=repr
        )

        # test for other users
        RegistrationUserAccess.objects.all().delete()
        qs = self.instance.get_editable_events_for_registration(total_qs)
        self.assertQuerySetEqual(qs, [], transform=repr)
