import logging
import uuid

from django_orghierarchy.models import Organization
from django.utils.translation import ugettext_lazy as _
from django.contrib.gis.db import models
from django.contrib.auth import get_user_model
from django.utils.encoding import smart_text
from django.utils.functional import cached_property
from django.contrib.auth.hashers import make_password

from rest_framework import authentication, exceptions
from events.models import DataSource
from helevents.models import User
from oidc_auth.authentication import JSONWebTokenAuthentication
from datetime import datetime

from .permissions import UserModelPermissionMixin

logger = logging.getLogger(__name__)


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


class OIDCAuthentication(JSONWebTokenAuthentication):
    provider_name = "oidc"

    @cached_property
    def auth_scheme(self):
        return 'Bearer'

    def authenticate(self, request):
        jwt_value = self.get_jwt_value(request)
        if jwt_value is None:
            return None

        try:
            payload = self.decode_jwt(jwt_value)
        except exceptions.AuthenticationFailed:
            logger.error("Invalid token signature")
            return None

        data_source = self.get_data_source(payload)
        if not data_source:
            return None

        try:
            self.validate_claims(payload)
        except exceptions.AuthenticationFailed:
            logger.error("Claims validation failed")
            return None

        user = self.get_or_create_user(payload, data_source)

        return user, OIDCAuth(data_source)

    def get_jwt_value(self, request):
        auth = authentication.get_authorization_header(request).split()

        if not auth or smart_text(auth[0]).lower() != self.auth_scheme.lower():
            return None

        if len(auth) == 1:
            raise exceptions.AuthenticationFailed(
                _("Invalid Authorization header. No credentials provided"))
        elif len(auth) > 2:
            raise exceptions.AuthenticationFailed(
                _("Invalid Authorization header. "
                  "Credentials string should not contain spaces."))

        return auth[1]

    def get_or_create_user(self, payload, data_source):
        sub = payload.get("sub")
        if not sub:
            raise  exceptions.AuthenticationFailed('Invalid payload. sub missing')

        email = payload.get("email")
        if not email:
            raise exceptions.AuthenticationFailed('Invalid payload. email missing')

        first_name = payload.get("given_name")
        if not first_name:
            raise exceptions.AuthenticationFailed('Invalid payload. first_name missing')

        last_name = payload.get("family_name")
        if not last_name:
            raise exceptions.AuthenticationFailed('Invalid payload. family_name missing')

        organization, _ = Organization.objects.get_or_create(
            parent_id=data_source.owner.id,
            origin_id="oidc:user:" + sub,
            data_source=data_source,
            name=sub
        )

        user = self.get_user_by_email(email)

        if not user:
            logger.info("OIDC user with email %s does not exist. Creating new user" % email)

            user = User.objects.create(
                email=email,
                password=make_password(None),
                is_superuser=False,
                is_staff=False,
                is_active=True,
                date_joined=datetime.utcnow(),
                uuid=str(uuid.uuid4()),
                username=email,
                first_name=first_name,
                last_name=last_name
            )
        else:
            logger.info("OIDC user with email %s already exist" % email)

        users_organizations = user.admin_organizations.all()

        if organization not in users_organizations:
            user.admin_organizations.add(organization)

        return user

    def get_user_by_email(self, email):
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None

    def get_data_source(self, payload):
        audiences = payload.get("aud")
        if not isinstance(audiences, list):
            audiences = [audiences]

        for audience in audiences:
            try:
                data_source = DataSource.objects.get(id=audience)
                return data_source
            except DataSource.DoesNotExist:
                pass

        return None


class OIDCAuthenticationUser(get_user_model(), UserModelPermissionMixin):
    data_source = models.OneToOneField(DataSource, on_delete=models.CASCADE, primary_key=True)

    def get_display_name(self):
        return 'OIDC user from data source %s' % self.data_source

    def __str__(self):
        return self.get_display_name()

    def get_default_organization(self):
        return self.data_source.owner

    @property
    def organization_memberships(self):
        if not self.data_source.owner:
            return Organization.objects.none()
        return Organization.objects.filter(id=self.data_source.owner.id)


class ApiKeyUser(get_user_model(), UserModelPermissionMixin):
    data_source = models.OneToOneField(DataSource, on_delete=models.CASCADE, primary_key=True)

    def get_display_name(self):
        return 'API key from data source %s' % self.data_source

    def __str__(self):
        return self.get_display_name()

    def get_default_organization(self):
        return self.data_source.owner

    def is_admin(self, publisher):
        return publisher in self.data_source.owner.get_descendants(include_self=True)

    def is_regular_user(self, publisher):
        return False

    @property
    def admin_organizations(self):
        if not self.data_source.owner:
            return Organization.objects.none()
        return Organization.objects.filter(id=self.data_source.owner.id)

    @property
    def organization_memberships(self):
        return Organization.objects.none()


class ExternalAuth(object):
    def __init__(self, data_source):
        self.data_source = data_source

    def get_authenticated_data_source(self):
        return self.data_source


class ApiKeyAuth(ExternalAuth):
    def __init__(self, data_source):
        super().__init__(data_source)


class OIDCAuth(ExternalAuth):
    def __init__(self, data_source):
        super().__init__(data_source)
