import logging

from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticatedOrReadOnly
from rest_framework.request import Request

from events import utils

from .auth import ApiKeyUser

logger = logging.getLogger(__name__)


class GuestPost(BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            return True
        else:
            return False


class GuestRetrieve(BasePermission):
    def has_permission(self, request, view):
        return view.action == "retrieve"


class IsReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class UserDataFromRequestMixin:
    """
    Cache utils.get_user_data_source_and_organization_from_request
    as the permission check may get called multiple times during a single
    request.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__cached = None

    def user_data_source_and_organization_from_request(self, request):
        if self.__cached:
            return self.__cached
        self.__cached = utils.get_user_data_source_and_organization_from_request(
            request
        )
        return self.__cached


class UserBelongsToOrganization(UserDataFromRequestMixin, BasePermission):
    message = "User doesn't belong to any organization"

    def has_permission(self, request, view):
        (
            __,
            user_organization,
        ) = self.user_data_source_and_organization_from_request(request)
        return bool(user_organization)


class IsObjectEditableByUser(BasePermission):
    message = "User is not allowed to edit this object"

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.can_be_edited_by(request.user)


class OrganizationUserCreatePermission(UserDataFromRequestMixin, BasePermission):
    message = "User is not allowed to edit this object"

    def has_permission(self, request, view):
        if request.method != "POST":
            return True

        user = request.user
        if user and user.is_anonymous:
            return False

        (
            __,
            user_organization,
        ) = self.user_data_source_and_organization_from_request(request)
        view_permits_regular_user_edit = getattr(
            view, "permit_regular_user_edit", False
        )
        return (
            user.is_superuser
            or user.is_admin_of(user_organization)
            or (
                view_permits_regular_user_edit
                and user.is_regular_user_of(user_organization)
            )
        )


IsObjectEditableByOrganizationUser = (
    IsObjectEditableByUser & OrganizationUserCreatePermission
)

OrganizationUserEditPermission = (
    IsReadOnly | UserBelongsToOrganization & IsObjectEditableByOrganizationUser
)


class DataSourceResourceEditPermission(
    UserDataFromRequestMixin, IsAuthenticatedOrReadOnly
):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        # PUT and DESTROY will be checked via has_object_permission
        if request.method != "POST":
            return True

        user_data_source, __ = self.user_data_source_and_organization_from_request(
            request
        )

        if not isinstance(request.user, ApiKeyUser):
            if not user_data_source.user_editable_resources:
                raise PermissionDenied(_("Data source is not editable"))

        return True

    def has_object_permission(self, request: Request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        user_data_source, __ = self.user_data_source_and_organization_from_request(
            request
        )

        if isinstance(request.user, ApiKeyUser):
            # allow updating only if the api key matches instance data source
            if obj.data_source != user_data_source:
                raise PermissionDenied(
                    _("Object data source does not match user data source")
                )
        else:
            # without api key, the user will have to be admin
            if (
                hasattr(obj, "is_user_editable_resources")
                and not obj.is_user_editable_resources()
            ):
                raise PermissionDenied(_("Data source is not editable"))

        return True


class DataSourceOrganizationEditPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            if settings.WEB_STORE_INTEGRATION_ENABLED and request.data.get(
                "web_store_merchants"
            ):
                return request.user.is_authenticated and request.user.is_superuser
            elif (
                request.user.is_authenticated
                and request.user.admin_organizations.exists()
            ):
                return True

            logging.info("User must be an admin to create an organization")
            return False

        return True

    def has_object_permission(self, request: Request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if (
            settings.WEB_STORE_INTEGRATION_ENABLED
            and request.method in ("PUT", "PATCH")
            and request.data.get("web_store_merchants")
        ):
            data_keys = request.data.keys()

            if len(data_keys) > 1:
                return request.user.is_superuser
            else:
                return request.user.is_superuser or request.user.is_financial_admin_of(
                    obj
                )

        return utils.organization_can_be_edited_by(obj, request.user)


class UserIsAdminInAnyOrganization(BasePermission):
    message = _("Only admins of any organization are allowed to see the content.")

    def has_permission(self, request, view):
        user = request.user

        if user.is_anonymous:
            return False

        return user.admin_organizations.exists()
