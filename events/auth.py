from django.contrib.auth.models import AnonymousUser
from rest_framework import authentication
from rest_framework import exceptions
from events.models import DataSource
from django.utils.translation import ugettext_lazy as _


class ApiKeyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        api_key = request.query_params.get('api_key')
        if not api_key:
            return None
        data_source = self.get_data_source(api_key=api_key)
        return ApiKeyUser(), ApiKeyAuth(data_source)

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


class ApiKeyUser(AnonymousUser):
    def is_authenticated(self):
        return True


class ApiKeyAuth(object):
    def __init__(self, data_source):
        self.data_source = data_source

    def get_authenticated_data_source(self):
        return self.data_source
