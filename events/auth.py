from django.contrib.auth import get_user_model
from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization
from helusers.oidc import ApiTokenAuthentication as HelApiTokenAuthentication
from rest_framework import authentication, exceptions

from events.models import DataSource
from helevents.models import UserModelPermissionMixin


class ApiTokenAuthentication(HelApiTokenAuthentication):
    def authenticate(self, request):
        """Extract the AMR claim from the authentication payload."""
        auth_data = super().authenticate(request)
        if not auth_data:
            return auth_data

        user, auth = auth_data

        if amr_claim := auth.data.get("amr"):
            user.token_amr_claim = amr_claim

        return user, auth


class ApiKeyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        # django converts 'apikey' to 'HTTP_APIKEY' outside runserver
        api_key = request.META.get("apikey") or request.META.get("HTTP_APIKEY")
        if not api_key:
            return None
        data_source = self.get_data_source(api_key=api_key)
        user = ApiKeyUser.objects.get_or_create(data_source=data_source)[0]
        return user, ApiKeyAuth(data_source)

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response, or `None` if the
        authentication scheme should return `403 Permission Denied` responses.
        """
        return "Api key authentication failed."

    @staticmethod
    def get_data_source(api_key):
        try:
            data_source = DataSource.objects.get(api_key=api_key)
        except DataSource.DoesNotExist:
            raise exceptions.AuthenticationFailed(
                _(
                    "Provided API key does not match any organization on record. "
                    "Please contact the API support staff to obtain a valid API key "
                    "and organization identifier for POSTing your events."
                )
            )
        return data_source


class ApiKeyUser(get_user_model(), UserModelPermissionMixin):
    data_source = models.OneToOneField(
        DataSource, on_delete=models.CASCADE, primary_key=True
    )

    def get_display_name(self):
        return "API key from data source %s" % self.data_source

    def __str__(self):
        return self.get_display_name()

    def get_default_organization(self):
        return self.data_source.owner

    def is_admin_of(self, publisher):
        if not self.data_source.owner_id:
            return False
        return publisher in self.data_source.owner.get_descendants(include_self=True)

    def is_registration_admin_of(self, publisher):
        return (
            self.is_admin_of(publisher) and self.data_source.user_editable_registrations
        )

    def is_regular_user_of(self, publisher):
        return False

    def is_registration_user_access_user_of(self, registration_user_accesses):
        return False

    @property
    def admin_organizations(self):
        if not self.data_source.owner:
            return Organization.objects.none()
        return Organization.objects.filter(id=self.data_source.owner.id)

    @property
    def organization_memberships(self):
        return Organization.objects.none()

    @property
    def apikey_registration_admin_organizations(self):
        if not (
            self.data_source.owner and self.data_source.user_editable_registrations
        ):
            return Organization.objects.none()
        return Organization.objects.filter(id=self.data_source.owner.id)

    def get_registration_admin_organizations_and_descendants(self):
        # returns registration admin organizations and their descendants
        return self._get_admin_organizations_and_descendants(
            "apikey_registration_admin_organizations"
        )

    @property
    def is_external(self):
        return False


class ApiKeyAuth(object):
    def __init__(self, data_source):
        self.data_source = data_source

    def get_authenticated_data_source(self):
        return self.data_source
