from django.utils.translation import gettext as _
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request

from events.auth import ApiKeyUser


class AuthenticatedGet(permissions.BasePermission):
    def has_permission(self, request, view):
        # Only authenticated users can get object
        return request.method != "GET" or request.user.is_authenticated

    def has_object_permission(self, request: Request, view, obj):
        user = request.user

        if request.method != "GET":
            return True

        if isinstance(user, ApiKeyUser):
            user_data_source, _ = view.user_data_source_and_organization
            # allow to view data only if the api key matches instance data source
            if obj.data_source != user_data_source:
                return False

        return obj.can_be_edited_by(request.user)


class AuthenticateWithCancellationCode(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user

        # Anonymous users can modified SignUp by cancellation_code
        if user.is_anonymous and request.method in ["DELETE", "PUT"]:
            return True

        # List view is not allowed with cancellation code
        if request.method == "GET" and not view.kwargs.get("pk"):
            return False

        return super().has_permission(request, view)

    def has_object_permission(self, request: Request, view, obj):
        user = request.user

        if not user.is_anonymous:
            return False

        code = request.GET.get("cancellation_code", None)
        if not code:
            raise PermissionDenied(_("cancellation_code parameter has to be provided"))
        if code != str(obj.cancellation_code):
            raise PermissionDenied(_("Cancellation code did not match"))
        return True
