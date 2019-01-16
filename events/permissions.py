from functools import reduce
from .models import PublicationStatus


class UserModelPermissionMixin:
    """Permission mixin for user models

    A mixin class that provides permission check methods
    for user models.
    """
    def is_admin(self, publisher):
        """Check if current user is an admin user of the publisher organization"""
        raise NotImplementedError()

    def is_regular_user(self, publisher):
        """Check if current user is a regular user of the publisher organization"""
        raise NotImplementedError()

    @property
    def admin_organizations(self):
        raise NotImplementedError()

    @property
    def organization_memberships(self):
        raise NotImplementedError()

    def can_edit_event(self, publisher, publication_status):
        """Check if current user can edit (create, change, modify)
        event with the given publisher and publication_status"""
        if self.is_admin(publisher):
            return True
        if self.is_regular_user(publisher) and publication_status == PublicationStatus.DRAFT:
            return True
        return False

    def get_editable_events(self, queryset):
        """Get editable events queryset from given queryset for current user"""
        return queryset.filter(
            publisher__in=self.get_admin_organizations_and_descendants()
        ).distinct() | queryset.filter(
            publication_status=PublicationStatus.DRAFT, publisher__in=self.organization_memberships.all()
        ).distinct()

    def get_admin_organizations_and_descendants(self):
        # returns admin organizations and their descendants
        if not self.admin_organizations.all():
            return []
        # regular admins have rights to all organizations below their level
        admin_orgs = []
        for admin_org in self.admin_organizations.all():
            admin_orgs.append(admin_org.get_descendants(include_self=True))
            if admin_org.replaced_by:
                # admins of replaced organizations have these rights, too!
                admin_orgs.append(admin_org.replaced_by.get_descendants(include_self=True))
        # for multiple admin_orgs, we have to combine the querysets and filter distinct
        return reduce(lambda a, b: a | b, admin_orgs).distinct()
