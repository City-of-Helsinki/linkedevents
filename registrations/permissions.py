from django.contrib.auth.models import AnonymousUser
from django.utils.translation import gettext as _
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request

from events.permissions import DataSourceResourceEditPermission


class SignUpPermission(DataSourceResourceEditPermission):
    def has_permission(self, request, view):
        user = request.user

        # All users can create SignUps
        if request.method == "POST":
            return True

        # Anonymous users can modified SignUp by cancellation_code
        if isinstance(user, AnonymousUser) and (request.method in ["DELETE", "PUT"]):
            return True

        # Only users with an organization can get signup list
        if request.method == "GET" and not view.kwargs.get("pk"):
            user_data_source, user_organization = view.user_data_source_and_organization
            if not user_organization:
                raise PermissionDenied(_("User doesn't belong to any organization"))

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

        if request.method == "GET":
            return self._has_data_source_permission(request, view, obj)

        return super().has_object_permission(request, view, obj)
