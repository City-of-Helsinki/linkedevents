from rest_framework import authentication
from rest_framework import exceptions
from events.models import DataSource
from django_orghierarchy.models import Organization
from django.utils.translation import ugettext_lazy as _
from django.contrib.gis.db import models
from django.contrib.auth import get_user_model

from .permissions import UserModelPermissionMixin


class ApiKeyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        # django converts 'apikey' to 'HTTP_APIKEY' outside runserver
        api_key = request.META.get('apikey') or request.META.get('HTTP_APIKEY')
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
            raise exceptions.AuthenticationFailed(_(
                "Provided API key does not match any organization on record. "
                "Please contact the API support staff to obtain a valid API key "
                "and organization identifier for POSTing your events."))
        return data_source


class ApiKeyUser(get_user_model(), UserModelPermissionMixin):
    data_source = models.OneToOneField(DataSource, on_delete=models.CASCADE, primary_key=True)

    def get_display_name(self):
        return 'API key from data source %s' % self.data_source

    def __str__(self):
        return self.get_display_name()

    def get_default_organization(self):
        return self.data_source.owner

    def is_admin(self, publisher):
        return self.data_source.owner == publisher

    def is_regular_user(self, publisher):
        return False

    def is_private_user(self, publisher):
        return False
        
    @property
    def admin_organizations(self):
        return Organization.objects.filter(id=self.data_source.owner.id)

    @property
    def organization_memberships(self):
        return Organization.objects.none()

    @property
    def public_memberships(self):
        return Organization.objects.none()


class ApiKeyAuth(object):
    def __init__(self, data_source):
        self.data_source = data_source

    def get_authenticated_data_source(self):
        return self.data_source
