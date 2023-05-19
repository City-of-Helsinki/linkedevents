from django.utils.translation import gettext as _
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticatedOrReadOnly
from rest_framework.request import Request

from events import utils


class GuestPost(BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            return True
        else:
            return False


class GuestRetrieve(BasePermission):
    def has_permission(self, request, view):
        return view.action == "retrieve"


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
        if request.method in permissions.SAFE_METHODS:
            return True

        return self._has_data_source_permission(request, view, obj)


class DataSourceOrganizationEditPermission(IsAuthenticatedOrReadOnly):
    def has_object_permission(self, request: Request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return utils.organization_can_be_edited_by(obj, request.user)


class UserIsAdminInAnyOrganization(BasePermission):
    message = _("Only admins of any organization are allowed to see the content.")

    def has_permission(self, request, view):
        user = request.user

        if user.is_anonymous:
            return False

        return user.admin_organizations.exists()
