from django.utils.translation import gettext as _
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from events.auth import ApiKeyUser
from registrations.models import SignUp


class CanCreateEditDeleteSignup(permissions.BasePermission):
    message: str = _(
        "Only authenticated users are able to access sign-ups. Viewing, editing and deleting are"
        "allowed only for admins of the publishing organization and for users that have created "
        "the sign-up."
    )

    def has_permission(self, request: Request, view: APIView) -> bool:
        return (
            request.method
            in permissions.SAFE_METHODS + ("POST", "PUT", "PATCH", "DELETE")
            and request.user.is_authenticated
        )

    def has_object_permission(
        self, request: Request, view: APIView, obj: SignUp
    ) -> bool:
        if isinstance(request.user, ApiKeyUser):
            user_data_source, _ = view.user_data_source_and_organization
            # allow only if the api key matches instance data source
            if obj.data_source != user_data_source:
                return False

        return obj.can_be_edited_by(request.user)


class RegistrationUserRetrievePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        # Only authenticated users can get object
        return view.action == "retrieve" or request.user.is_authenticated

    def has_object_permission(self, request: Request, view, obj):
        user = request.user
        if view.action != "retrieve":
            return False

        registration_user_emails = [
            u.email for u in obj.registration.registration_users.all()
        ]
        return user.email in registration_user_emails