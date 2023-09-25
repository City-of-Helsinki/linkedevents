from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from events.auth import ApiKeyUser
from events.permissions import UserDataFromRequestMixin
from registrations.models import Registration, SignUp


class CanAccessRegistration(UserDataFromRequestMixin, permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if view.action == "retrieve":
            return True

        if not request.user.is_authenticated:
            return False

        if request.method == "POST":
            (
                __,
                user_organization,
            ) = self.user_data_source_and_organization_from_request(request)
            return (
                request.user.is_superuser
                or request.user.is_admin_of(user_organization)
                or request.user.is_registration_admin_of(user_organization)
            )

        if request.method in ("PUT", "PATCH", "DELETE"):
            (
                __,
                user_organization,
            ) = self.user_data_source_and_organization_from_request(request)
            return bool(user_organization)

        return request.method in permissions.SAFE_METHODS

    def has_object_permission(
        self, request: Request, view: APIView, obj: Registration
    ) -> bool:
        if view.action == "retrieve":
            return True

        if isinstance(request.user, ApiKeyUser):
            user_data_source, _ = view.user_data_source_and_organization
            # allow only if the api key matches instance data source
            if obj.data_source != user_data_source:
                return False

        return obj.can_be_edited_by(request.user)


class CanAccessSignup(UserDataFromRequestMixin, permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user.is_authenticated:
            return False

        if request.method == "POST":
            (
                __,
                user_organization,
            ) = self.user_data_source_and_organization_from_request(request)
            return request.user.is_superuser or request.user.is_registration_admin_of(
                user_organization
            )

        if request.method in ("PATCH", "PUT", "DELETE"):
            (
                __,
                user_organization,
            ) = self.user_data_source_and_organization_from_request(request)
            return bool(user_organization)

        return request.method in permissions.SAFE_METHODS

    def has_object_permission(
        self, request: Request, view: APIView, obj: SignUp
    ) -> bool:
        if isinstance(request.user, ApiKeyUser):
            user_data_source, _ = view.user_data_source_and_organization
            # allow only if the api key matches instance data source
            if obj.data_source != user_data_source:
                return False

        if request.method == "DELETE":
            return obj.can_be_deleted_by(request.user)

        return obj.can_be_edited_by(request.user)
