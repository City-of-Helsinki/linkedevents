import logging
from functools import reduce

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.functional import cached_property
from django_orghierarchy.models import Organization
from helsinki_gdpr.models import SerializableMixin
from helusers.models import AbstractUser

from events.models import PublicationStatus
from registrations.models import RegistrationUserAccess
from registrations.utils import has_allowed_substitute_user_email_domain

logger = logging.getLogger(__name__)


class UserModelPermissionMixin:
    """Permission mixin for user models

    A mixin class that provides permission check methods
    for user models.
    """

    @property
    def token_amr_claim(self) -> list[str]:
        claim = getattr(self, "_token_amr_claim", None)
        if claim is None:
            logger.warning(
                "User.token_amr_claim used without a request or authentication.",
                stack_info=True,
                stacklevel=2,
            )

        if not claim:
            return []

        if not isinstance(claim, list):
            # Tunnistamo returns amr-claim as string instead of list as it should
            # be according to the spec. This is a workaround for that.
            claim = [claim]
        return claim

    @token_amr_claim.setter
    def token_amr_claim(self, value: str):
        self._token_amr_claim = value

    @property
    def is_strongly_identified(self) -> bool:
        """Check if the user is strongly identified"""

        return any(
            login_method in settings.STRONG_IDENTIFICATION_AUTHENTICATION_METHODS
            for login_method in self.token_amr_claim
        )

    @property
    def is_external(self):
        """Check if the user is an external user"""
        raise NotImplementedError()

    @property
    def is_substitute_user(self):
        """Check if the user is a substitute user of any registration"""
        raise NotImplementedError()

    def is_admin_of(self, publisher):
        """Check if current user is an admin user of the publisher organization"""
        raise NotImplementedError()

    def is_registration_admin_of(self, publisher):
        """Check if current user is a registration admin user of the publisher organization"""  # noqa: E501
        raise NotImplementedError()

    def is_financial_admin_of(self, publisher):
        """Check if current user is a financial admin user of the publisher organization"""  # noqa: E501
        raise NotImplementedError()

    def is_regular_user_of(self, publisher):
        """Check if current user is a regular user of the publisher organization"""
        raise NotImplementedError()

    def is_registration_user_access_user_of(self, registration_user_accesses):
        """Check if current user can be found in registration user accesses"""
        raise NotImplementedError()

    def is_substitute_user_of(self, registration_user_accesses):
        """Check if current user is a substitute user for registrations"""
        raise NotImplementedError()

    def is_contact_person_of(self, signup_or_group):
        """Check if current user is the contact person of a signup or a signup group"""
        raise NotImplementedError()

    @property
    def admin_organizations(self):
        """
        Get a queryset of organizations that the user is an admin of.

        Is replaced by django_orghierarchy.models.Organization's
        admin_organizations relation unless implemented in a subclass.
        """
        raise NotImplementedError()

    @property
    def registration_admin_organizations(self):
        """
        Get a queryset of organizations that the user is a registration admin of.
        Is replaced by django_orghierarchy.models.Organization's
        registration_admin_organizations relation unless implemented in a subclass.
        """
        raise NotImplementedError()

    @property
    def financial_admin_organizations(self):
        """
        Get a queryset of organizations that the user is a financial admin of.
        """
        raise NotImplementedError()

    @property
    def organization_memberships(self):
        """
        Get a queryset of organizations that the user is a member of.

        Is replaced by django_orghierarchy.models.Organization's
        organization_memberships relation unless implemented
        in a subclass.
        """
        raise NotImplementedError()

    def can_create_event(self, publisher, publication_status):
        """Check if current user can create an event with the given publisher and publication_status"""  # noqa: E501
        return self.can_edit_event(publisher, publication_status, created_by=self)

    def can_edit_event(self, publisher, publication_status, created_by=None):
        """Check if current user can edit an event with the given publisher and publication_status"""  # noqa: E501
        if self.is_admin_of(publisher):
            return True

        # Non-admins can only edit drafts.
        if publication_status == PublicationStatus.DRAFT:
            if settings.ENABLE_EXTERNAL_USER_EVENTS and (
                publisher is None or publisher.id == settings.EXTERNAL_USER_PUBLISHER_ID
            ):
                # External users can only edit their own drafts from the default
                # organization.
                return self.is_external and created_by == self
            else:
                # Regular users can edit drafts from organizations they are members of.
                return self.is_regular_user_of(publisher)

        return False

    def get_editable_events(self, queryset):
        """Get editable events queryset from given queryset for current user"""
        if self.is_external:
            if settings.ENABLE_EXTERNAL_USER_EVENTS:
                # External users can only edit their own drafts from the default
                # organization.
                return queryset.filter(
                    created_by=self,
                    publisher__id=settings.EXTERNAL_USER_PUBLISHER_ID,
                    publication_status=PublicationStatus.DRAFT,
                )
            else:
                return queryset.none()

        publishers = self.get_admin_organizations_and_descendants()
        # distinct is not needed here, as admin_orgs and memberships should not overlap
        return queryset.filter(publisher__in=publishers) | queryset.filter(
            publication_status=PublicationStatus.DRAFT,
            publisher__in=self.organization_memberships.all(),
        )

    def get_editable_events_for_registration(self, queryset):
        publishers = (
            self.get_admin_organizations_and_descendants()
            | self.get_registration_admin_organizations_and_descendants()
        )

        if has_allowed_substitute_user_email_domain(self.email):
            # Show also events where the user is a Helsinki substitute user.
            return queryset.filter(publisher__in=publishers) | queryset.filter(
                registration__registration_user_accesses__email=self.email,
                registration__registration_user_accesses__is_substitute_user=True,
            )
        else:
            return queryset.filter(publisher__in=publishers)

    def _get_admin_tree_ids(self, admin_queryset):
        # returns tree ids for all admin organizations and their replacements
        admin_tree_ids = admin_queryset.values("tree_id")
        admin_replaced_tree_ids = admin_queryset.filter(
            replaced_by__isnull=False
        ).values("replaced_by__tree_id")
        return set(value["tree_id"] for value in admin_tree_ids) | set(
            value["replaced_by__tree_id"] for value in admin_replaced_tree_ids
        )

    def get_admin_tree_ids(self):
        # returns tree ids for all normal admin organizations and their replacements
        admin_queryset = self.admin_organizations.filter(
            internal_type="normal"
        ).select_related("replaced_by")
        return self._get_admin_tree_ids(admin_queryset)

    def get_registration_admin_tree_ids(self):
        # returns tree ids for all normal registration admin organizations and
        # their replacements
        admin_queryset = self.registration_admin_organizations.filter(
            internal_type="normal"
        ).select_related("replaced_by")
        return self._get_admin_tree_ids(admin_queryset)

    def _get_admin_organizations_and_descendants(self, relation_name: str):
        # returns admin organizations and their descendants
        admin_rel = getattr(self, relation_name, None)
        if not admin_rel or not admin_rel.all():
            return Organization.objects.none()
        # regular admins have rights to all organizations below their level
        admin_orgs = []
        for admin_org in admin_rel.all():
            admin_orgs.append(admin_org.get_descendants(include_self=True))
            if admin_org.replaced_by:
                # admins of replaced organizations have these rights, too!
                admin_orgs.append(
                    admin_org.replaced_by.get_descendants(include_self=True)
                )
        # for multiple admin_orgs, we have to combine the querysets and filter distinct
        return reduce(lambda a, b: a | b, admin_orgs).distinct()

    def get_admin_organizations_and_descendants(self):
        # returns admin organizations and their descendants
        return self._get_admin_organizations_and_descendants("admin_organizations")

    def get_registration_admin_organizations_and_descendants(self):
        # returns registration admin organizations and their descendants
        return self._get_admin_organizations_and_descendants(
            "registration_admin_organizations"
        )

    def get_financial_admin_organizations_and_descendants(self):
        # returns financial admin organizations and their descendants
        return self._get_admin_organizations_and_descendants(
            "financial_admin_organizations"
        )


class User(AbstractUser, UserModelPermissionMixin, SerializableMixin):
    registration_admin_organizations = models.ManyToManyField(
        Organization, blank=True, related_name="registration_admin_users"
    )

    financial_admin_organizations = models.ManyToManyField(
        Organization, blank=True, related_name="financial_admin_users"
    )

    serialize_fields = (
        {"name": "id"},
        {"name": "first_name"},
        {"name": "last_name"},
        {"name": "email"},
        {"name": "signup_created_by"},
        {"name": "events_event_created_by"},
        {"name": "publisher_organizations"},
    )

    def __str__(self):
        return " - ".join([self.get_display_name(), self.email])

    @property
    def publisher_organizations(self):
        """
        Organizations where user is part of as admin or regular user.
        This is used in the gdpr api user data serialization.
        """
        return [
            org.serialize()
            for org in SerializablePublisher.objects.filter(
                Q(admin_users=self) | Q(regular_users=self)
            )
        ]

    def get_display_name(self) -> str:
        return "{0} {1}".format(self.first_name, self.last_name).strip()

    def get_default_organization(self):
        admin_org = (
            self.admin_organizations.filter(
                replaced_by__isnull=True,
            )
            .order_by("created_time")
            .first()
        )

        registration_admin_org = (
            self.registration_admin_organizations.filter(
                replaced_by__isnull=True,
            )
            .order_by("created_time")
            .first()
        )

        financial_admin_org = (
            self.financial_admin_organizations.filter(
                replaced_by__isnull=True,
            )
            .order_by("created_time")
            .first()
        )

        regular_org = (
            self.organization_memberships.filter(
                replaced_by__isnull=True,
            )
            .order_by("created_time")
            .first()
        )

        return admin_org or registration_admin_org or financial_admin_org or regular_org

    def is_admin_of(self, publisher):
        if publisher is None:
            return False
        return publisher in self.get_admin_organizations_and_descendants()

    def is_registration_admin_of(self, publisher):
        if publisher is None:
            return False
        return publisher in self.get_registration_admin_organizations_and_descendants()

    def is_financial_admin_of(self, publisher):
        if publisher is None:
            return False
        return publisher in self.get_financial_admin_organizations_and_descendants()

    def is_regular_user_of(self, publisher):
        if publisher is None:
            return False
        return self.organization_memberships.filter(id=publisher.id).exists()

    def is_registration_user_access_user_of(self, registration_user_accesses):
        """Check if current user can be found in registration user accesses"""
        return (
            self.is_strongly_identified
            and registration_user_accesses.filter(email=self.email).exists()
        )

    def is_substitute_user_of(self, registration_user_accesses):
        """Check if current user is a substitute user for registrations"""
        if not has_allowed_substitute_user_email_domain(self.email):
            return False

        return registration_user_accesses.filter(
            email=self.email, is_substitute_user=True
        ).exists()

    def is_contact_person_of(self, signup_or_group):
        """Check if current user is the contact person of a signup or a signup group"""
        if not signup_or_group.actual_contact_person:
            return False

        return (
            self.is_strongly_identified
            and signup_or_group.actual_contact_person.user_id == self.id
        )

    @cached_property
    def is_external(self) -> bool:
        if any(
            login_method in settings.NON_EXTERNAL_AUTHENTICATION_METHODS
            for login_method in self.token_amr_claim
        ):
            return False

        return (
            not self.organization_memberships.exists()
            and not self.admin_organizations.exists()
            and not self.registration_admin_organizations.exists()
            and not self.financial_admin_organizations.exists()
        )

    @cached_property
    def is_substitute_user(self) -> bool:
        if not has_allowed_substitute_user_email_domain(self.email):
            return False

        return RegistrationUserAccess.objects.filter(
            email=self.email, is_substitute_user=True
        ).exists()


class SerializablePublisher(Organization, SerializableMixin):
    """Organization proxy model containing gdpr api serialization."""

    class Meta:
        proxy = True

    serialize_fields = ({"name": "id"}, {"name": "name"})
