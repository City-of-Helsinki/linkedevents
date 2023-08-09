from django.utils.translation import gettext as _
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from registrations.models import SignUp


class CanCreateSignUp(permissions.BasePermission):
    message: str = _("Only authenticated users are allowed to create sign-ups")

    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.method == "POST" and request.user.is_authenticated


class CanReadUpdateDeleteSignup(permissions.BasePermission):
    message: str = _(
        "Only authenticated users that are admins in the publishing organization or"
        "that have created the sign-up are allowed to view and edit it"
    )

    def has_permission(self, request: Request, view: APIView) -> bool:
        return (
            request.method in ("GET", "PUT", "PATCH", "DELETE")
            and request.user.is_authenticated
        )

    def has_object_permission(
        self, request: Request, view: APIView, obj: SignUp
    ) -> bool:
        return obj.can_be_edited_by(request.user)
