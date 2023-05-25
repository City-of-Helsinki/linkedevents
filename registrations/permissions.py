from django.contrib.auth.models import AnonymousUser
from django.utils.translation import gettext as _
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request

from events.auth import ApiKeyUser


class AuthenticatedGet(permissions.BasePermission):
    def has_permission(self, request, view):
        # Only authenticated users can get object
        if request.method == "GET":
            user = request.user

            if isinstance(user, AnonymousUser):
                return False

        return super().has_permission(request, view)

    def has_object_permission(self, request: Request, view, obj):
        user = request.user

        if request.method == "GET":
            if not obj.can_be_edited_by(request.user):
                return False

            if isinstance(user, ApiKeyUser):
                user_data_source, _ = view.user_data_source_and_organization
                # allow updating only if the api key matches instance data source
                if obj.data_source != user_data_source:
                    return False

        return True


class AuthenticateWithCancellationCode(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user

        # Anonymous users can modified SignUp by cancellation_code
        if isinstance(user, AnonymousUser) and (request.method in ["DELETE", "PUT"]):
            return True

        # List view is not allowed with cancellation code
        if request.method == "GET" and not view.kwargs.get("pk"):
            return False

        return super().has_permission(request, view)

    def has_object_permission(self, request: Request, view, obj):
        user = request.user

        if isinstance(user, AnonymousUser):
            code = request.GET.get("cancellation_code", None)

            if not code:
                raise PermissionDenied(
                    _("cancellation_code parameter has to be provided")
                )

            if code != str(obj.cancellation_code):
                raise PermissionDenied(_("Cancellation code did not match"))

            return True

        return False
