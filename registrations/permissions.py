from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from events.auth import ApiKeyUser
from events.permissions import UserDataFromRequestMixin
from registrations.models import PriceGroup, Registration, SignUp, SignUpGroup


class SignUpPermissionMixin:
    @staticmethod
    def _has_signup_admin_permissions(request: Request, obj: SignUp | SignUpGroup):
        return (
            request.user.is_superuser
            or request.user.is_registration_admin_of(obj.publisher)
            or (
                request.user.is_admin_of(obj.publisher)
                and obj.registration.created_by_id == request.user.id
            )
            or request.user.is_substitute_user_of(
                obj.registration.registration_user_accesses
            )
            or request.user.is_contact_person_of(obj)
        )

    @staticmethod
    def _can_use_access_code(request: Request, obj: SignUp | SignUpGroup):
        return (
            request.method == "GET"
            and request.user.is_strongly_identified
            and obj.actual_contact_person is not None
            and obj.actual_contact_person.check_access_code(
                request.GET.get("access_code")
            )
        )


class RegistrationBasePermission(UserDataFromRequestMixin, permissions.BasePermission):
    pass


class CanAccessRegistration(RegistrationBasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if view.action == "retrieve":
            return True

        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if request.method == "POST":
            (
                __,
                user_organization,
            ) = self.user_data_source_and_organization_from_request(request)
            return request.user.is_admin_of(
                user_organization
            ) or request.user.is_registration_admin_of(user_organization)

        if request.method in ("PUT", "PATCH", "DELETE"):
            (
                __,
                user_organization,
            ) = self.user_data_source_and_organization_from_request(request)
            return bool(user_organization) or request.user.is_substitute_user

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


class CanAccessRegistrationSignups(RegistrationBasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.method == "GET" and request.user.is_authenticated

    def has_object_permission(
        self, request: Request, view: APIView, obj: Registration
    ) -> bool:
        user = request.user

        if isinstance(user, ApiKeyUser):
            user_data_source, _ = view.user_data_source_and_organization
            # allow only if the api key matches instance data source
            if obj.data_source != user_data_source:
                return False

        return (
            user.is_superuser
            or user.is_registration_admin_of(obj.publisher)
            or (user.is_admin_of(obj.publisher) and obj.created_by_id == user.id)
            or user.is_substitute_user_of(obj.registration_user_accesses)
            or user.is_registration_user_access_user_of(obj.registration_user_accesses)
        )


class CanAccessSignup(SignUpPermissionMixin, RegistrationBasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.user.is_authenticated

    @staticmethod
    def _has_object_update_permission(request: Request, obj: SignUp) -> bool:
        if request.user.is_registration_user_access_user_of(
            obj.registration.registration_user_accesses
        ):
            # Strongly identified registration user can only change presence_status
            # and nothing else.
            data_keys = set(request.data.keys())
            return (
                obj.created_by_id == request.user.id
                or data_keys == {"id", "presence_status"}
                or data_keys == {"presence_status"}
            )
        elif obj.created_by_id == request.user.id:
            # User who created the signup, and is not one of the signup admins,
            # is allowed to change all other data except presence_status.
            return "presence_status" not in request.data.keys()

        return False

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

        if request.method in ("PUT", "PATCH"):
            return self._has_signup_admin_permissions(
                request, obj
            ) or self._has_object_update_permission(request, obj)

        return obj.can_be_edited_by(request.user) or self._can_use_access_code(
            request, obj
        )


class CanAccessSignupGroup(CanAccessSignup):
    @staticmethod
    def _has_object_update_permission(request: Request, obj: SignUpGroup) -> bool:
        def get_signups_keys():
            keys = set()
            for signup in request.data.get("signups", []):
                keys |= set(signup.keys())
            return keys

        if request.user.is_registration_user_access_user_of(
            obj.registration.registration_user_accesses
        ):
            # Strongly identified registration user can only change presence_status
            # and nothing else.
            data_keys = get_signups_keys()
            return (
                obj.created_by_id == request.user.id
                or data_keys
                == {
                    "id",
                    "registration",
                    "presence_status",
                }
                or data_keys == {"id", "presence_status"}
            )
        elif obj.created_by_id == request.user.id:
            # User who created the signup, and is not one of the signup admins,
            # is allowed to change all other data except presence_status.
            data_keys = get_signups_keys()
            return "presence_status" not in data_keys

        return False


class CanAccessPriceGroups(RegistrationBasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if request.method == "POST":
            (
                __,
                user_organization,
            ) = self.user_data_source_and_organization_from_request(request)
            return request.user.is_financial_admin_of(user_organization)

        return True

    def has_object_permission(
        self, request: Request, view: APIView, obj: PriceGroup
    ) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.is_superuser or request.user.is_financial_admin_of(
            obj.publisher
        )
