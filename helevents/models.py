import logging
from functools import reduce

from django.conf import settings
from django.db import models
from django.utils.functional import cached_property
from django_orghierarchy.models import Organization
from helusers.models import AbstractUser

from events.models import PublicationStatus

logger = logging.getLogger(__name__)


class UserModelPermissionMixin:
    """Permission mixin for user models

    A mixin class that provides permission check methods
    for user models.
    """

    @property
    def token_amr_claim(self) -> str:
        claim = getattr(self, "_token_amr_claim", None)
        if claim is None:
            logger.warning(
                "User.token_amr_claim used without a request or authentication.",
                stack_info=True,
                stacklevel=2,
            )

        return claim

    @token_amr_claim.setter
    def token_amr_claim(self, value: str):
        self._token_amr_claim = value

    @property
    def is_strongly_identified(self):
        """Check if the user is strongly identified"""
        return (
            self.token_amr_claim
            in settings.STRONG_IDENTIFICATION_AUTHENTICATION_METHODS
        )

    @cached_property
    def is_external(self):
        """Check if the user is an external user"""

        if self.token_amr_claim in settings.NON_EXTERNAL_AUTHENTICATION_METHODS:
            return False

        return (
            not self.organization_memberships.exists()
            and not self.admin_organizations.exists()
        )

    def is_admin_of(self, publisher):
        """Check if current user is an admin user of the publisher organization"""
        raise NotImplementedError()

    def is_registration_admin_of(self, publisher):
        """Check if current user is a registration admin user of the publisher organization"""
        raise NotImplementedError()

    def is_regular_user_of(self, publisher):
        """Check if current user is a regular user of the publisher organization"""
        raise NotImplementedError()

    def is_registration_user_access_user_of(self, registration_user_accesses):
        """Check if current user can be found in registration user accesses"""
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
    def organization_memberships(self):
        """
        Get a queryset of organizations that the user is a member of.

        Is replaced by django_orghierarchy.models.Organization's
        organization_memberships relation unless implemented
        in a subclass.
        """
        raise NotImplementedError()

    def can_create_event(self, publisher, publication_status):
        """Check if current user can create an event with the given publisher and publication_status"""
        return self.can_edit_event(publisher, publication_status, created_by=self)

    def can_edit_event(self, publisher, publication_status, created_by=None):
        """Check if current user can edit an event with the given publisher and publication_status"""
        if self.is_admin_of(publisher):
            return True

        # Non-admins can only edit drafts.
        if publication_status == PublicationStatus.DRAFT:
            if settings.ENABLE_EXTERNAL_USER_EVENTS and (
                publisher is None or publisher.id == settings.EXTERNAL_USER_PUBLISHER_ID
            ):
                # External users can only edit their own drafts from the default organization.
                return self.is_external and created_by == self
            else:
                # Regular users can edit drafts from organizations they are members of.
                return self.is_regular_user_of(publisher)

        return False

    def get_editable_events(self, queryset):
        """Get editable events queryset from given queryset for current user"""
        if self.is_external:
            if settings.ENABLE_EXTERNAL_USER_EVENTS:
                # External users can only edit their own drafts from the default organization.
                return queryset.filter(
                    created_by=self,
                    publisher__id=settings.EXTERNAL_USER_PUBLISHER_ID,
                    publication_status=PublicationStatus.DRAFT,
                )
            else:
                return queryset.none()

        # distinct is not needed here, as admin_orgs and memberships should not overlap
        return queryset.filter(
            publisher__in=self.get_admin_organizations_and_descendants()
        ) | queryset.filter(
            publication_status=PublicationStatus.DRAFT,
            publisher__in=self.organization_memberships.all(),
        )

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
        # returns tree ids for all normal registration admin organizations and their replacements
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


class User(AbstractUser, UserModelPermissionMixin):
    registration_admin_organizations = models.ManyToManyField(
        Organization, blank=True, related_name="registration_admin_users"
    )

    def __str__(self):
        return " - ".join([self.get_display_name(), self.email])

    def get_display_name(self):
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

        regular_org = (
            self.organization_memberships.filter(
                replaced_by__isnull=True,
            )
            .order_by("created_time")
            .first()
        )

        return admin_org or registration_admin_org or regular_org

    def is_admin_of(self, publisher):
        if publisher is None:
            return False
        return publisher in self.get_admin_organizations_and_descendants()

    def is_registration_admin_of(self, publisher):
        if publisher is None:
            return False
        return publisher in self.get_registration_admin_organizations_and_descendants()

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
