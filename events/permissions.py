from functools import reduce

from django.utils.translation import gettext as _
from django_orghierarchy.models import Organization
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticatedOrReadOnly
from rest_framework.request import Request

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
        if (
            self.is_regular_user(publisher)
            and publication_status == PublicationStatus.DRAFT
        ):
            return True
        return False

    def get_editable_events(self, queryset):
        """Get editable events queryset from given queryset for current user"""
        # distinct is not needed here, as admin_orgs and memberships should not overlap
        return queryset.filter(
            publisher__in=self.get_admin_organizations_and_descendants()
        ) | queryset.filter(
            publication_status=PublicationStatus.DRAFT,
            publisher__in=self.organization_memberships.all(),
        )

    def get_admin_tree_ids(self):
        # returns tree ids for all normal admin organizations and their replacements
        admin_queryset = self.admin_organizations.filter(
            internal_type="normal"
        ).select_related("replaced_by")
        admin_tree_ids = admin_queryset.values("tree_id")
        admin_replaced_tree_ids = admin_queryset.filter(
            replaced_by__isnull=False
        ).values("replaced_by__tree_id")
        return set(value["tree_id"] for value in admin_tree_ids) | set(
            value["replaced_by__tree_id"] for value in admin_replaced_tree_ids
        )

    def get_admin_organizations_and_descendants(self):
        # returns admin organizations and their descendants
        if not self.admin_organizations.all():
            return Organization.objects.none()
        # regular admins have rights to all organizations below their level
        admin_orgs = []
        for admin_org in self.admin_organizations.all():
            admin_orgs.append(admin_org.get_descendants(include_self=True))
            if admin_org.replaced_by:
                # admins of replaced organizations have these rights, too!
                admin_orgs.append(
                    admin_org.replaced_by.get_descendants(include_self=True)
                )
        # for multiple admin_orgs, we have to combine the querysets and filter distinct
        return reduce(lambda a, b: a | b, admin_orgs).distinct()


class GuestPost(BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            return True
        else:
            return False


class GuestRetrieve(BasePermission):
    def has_permission(self, request, view):
        return request.method == "GET" and view.kwargs.get("pk")


class DataSourceResourceEditPermission(IsAuthenticatedOrReadOnly):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        if request.method not in permissions.SAFE_METHODS:
            user_data_source, user_organization = view.user_data_source_and_organization
            if not user_organization:
                raise PermissionDenied(_("User doesn't belong to any organization"))

        # PUT and DESTROY will be checked via has_object_permission
        if request.method == "POST":
            return self._has_data_source_permission(request, view)

        return True

    def _has_data_source_permission(self, request, view, obj=None):
        if obj is None:
            return self._has_data_source_permission_without_obj(request, view)

        return self._has_data_source_permission_with_obj(request, view, obj)

    def _has_data_source_permission_without_obj(self, request, view):
        from .auth import ApiKeyUser

        user = request.user
        user_data_source, user_organization = view.user_data_source_and_organization
        permit_regular_user_edit = getattr(view, "permit_regular_user_edit", False)
        permit_user_edit = (
            user.is_superuser
            or user.is_admin(user_organization)
            or (permit_regular_user_edit and user.is_regular_user(user_organization))
        )
        if not permit_user_edit:
            raise PermissionDenied(_("User is not allowed to edit this object"))

        if not isinstance(user, ApiKeyUser):
            if not user_data_source.user_editable_resources:
                raise PermissionDenied(_("Data source is not editable"))

        return True

    def _has_data_source_permission_with_obj(self, request, view, obj):
        from .auth import ApiKeyUser

        user = request.user
        user_data_source, user_organization = view.user_data_source_and_organization
        if not obj.can_be_edited_by(request.user):
            raise PermissionDenied(_("User is not allowed to edit this object"))

        if isinstance(user, ApiKeyUser):
            # allow updating only if the api key matches instance data source
            if obj.data_source != user_data_source:
                raise PermissionDenied(
                    _("Object data source does not match user data source")
                )
        else:
            # without api key, the user will have to be admin
            if not obj.is_user_editable_resources():
                raise PermissionDenied(_("Data source is not editable"))

        return True

    def has_object_permission(self, request: Request, view, obj):

        if not super().has_object_permission(request, view, obj):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return self._has_data_source_permission(request, view, obj)


class DataSourceOrganizationEditPermission(IsAuthenticatedOrReadOnly):
    def has_permission(self, request, view):
        return super().has_permission(request, view)

    def has_object_permission(self, request: Request, view, obj):
        from .api import organization_can_be_edited_by

        if not super().has_object_permission(request, view, obj):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return organization_can_be_edited_by(obj, request.user)


class UserIsAdminInAnyOrganization(BasePermission):
    message = _("Only admins of any organization are allowed to see the content.")

    def has_permission(self, request, view):
        user = request.user

        if user.is_anonymous:
            return False

        return user.admin_organizations.exists()
