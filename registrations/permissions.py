from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from events.auth import ApiKeyUser
from registrations.models import Registration, SignUp


class CanAccessRegistration(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return (
            request.method
            in permissions.SAFE_METHODS + ("POST", "PUT", "PATCH", "DELETE")
            and request.user.is_authenticated
        )

    def has_object_permission(
        self, request: Request, view: APIView, obj: Registration
    ) -> bool:
        if isinstance(request.user, ApiKeyUser):
            user_data_source, _ = view.user_data_source_and_organization
            # allow only if the api key matches instance data source
            if obj.data_source != user_data_source:
                return False

        conditions = [obj.can_be_edited_by(request.user)]
        if request.method == "GET":
            conditions.append(obj.created_by_id == request.user.id)
        return any(conditions)


class CanAccessSignup(permissions.BasePermission):
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

        if request.method == "DELETE":
            return obj.can_be_deleted_by(request.user)

        return obj.can_be_edited_by(request.user)
