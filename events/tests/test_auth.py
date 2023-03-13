import datetime
import uuid

import pytest
from django.test import RequestFactory, TestCase
from django_orghierarchy.models import Organization
from helusers.settings import api_token_auth_settings
from jose import jwt

from events.models import DataSource
from helevents.tests.factories import UserFactory

from ..auth import ApiKeyUser, LinkedEventsApiOidcAuthentication
from .keys import rsa_key

DEFAULT_ORGANIZATION_ID = "others"

req_mock = None


@pytest.fixture(autouse=True)
def global_requests_mock(requests_mock):
    global req_mock
    req_mock = requests_mock
    yield requests_mock

    req_mock = None


def get_api_token_for_user_with_scopes(user_uuid, scopes: list):
    """Build a proper auth token with desired scopes."""
    audience = api_token_auth_settings.AUDIENCE
    issuer = api_token_auth_settings.ISSUER
    auth_field = api_token_auth_settings.API_AUTHORIZATION_FIELD
    config_url = f"{issuer}/.well-known/openid-configuration"
    jwks_url = f"{issuer}/jwks"

    configuration = {
        "issuer": issuer,
        "jwks_uri": jwks_url,
    }

    keys = {"keys": [rsa_key.public_key_jwk]}

    now = datetime.datetime.now()
    expire = now + datetime.timedelta(days=14)

    jwt_data = {
        "iss": issuer,
        "aud": audience,
        "sub": str(user_uuid),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        auth_field: scopes,
    }
    encoded_jwt = jwt.encode(
        jwt_data, key=rsa_key.private_key_pem, algorithm=rsa_key.jose_algorithm
    )

    req_mock.get(config_url, json=configuration)
    req_mock.get(jwks_url, json=keys)

    auth_header = f"{api_token_auth_settings.AUTH_SCHEME} {encoded_jwt}"

    return auth_header


def do_authentication(user_uuid):
    auth = LinkedEventsApiOidcAuthentication()

    auth_header = get_api_token_for_user_with_scopes(
        user_uuid, [api_token_auth_settings.API_SCOPE_PREFIX]
    )

    rf = RequestFactory()
    request = rf.get("/path", HTTP_AUTHORIZATION=auth_header)

    return auth.authenticate(request)


class TestApiKeyUser(TestCase):
    def setUp(self):
        self.data_source = DataSource.objects.create(
            id="ds",
            name="data-source",
        )
        self.org_1 = Organization.objects.create(
            data_source=self.data_source,
            origin_id="org-1",
        )
        self.org_2 = Organization.objects.create(
            data_source=self.data_source,
            origin_id="org-2",
            replaced_by=self.org_1,
        )
        self.data_source.owner = self.org_1
        self.data_source.save()

        self.user = ApiKeyUser.objects.create(
            username="testuser",
            data_source=self.data_source,
        )

    def test_is_admin(self):
        is_admin = self.user.is_admin(self.org_1)
        self.assertTrue(is_admin)

        is_admin = self.user.is_admin(self.org_2)
        self.assertFalse(is_admin)

    def test_is_regular_user(self):
        is_regular_user = self.user.is_regular_user(self.org_1)
        self.assertFalse(is_regular_user)

        is_regular_user = self.user.is_regular_user(self.org_2)
        self.assertFalse(is_regular_user)


@pytest.mark.django_db
def test_valid_jwt_is_accepted():
    """JWT generated in tests has a valid signature and is accepted."""
    user_uuid = uuid.UUID("b7a35517-eb1f-46c9-88bf-3206fb659c3c")
    user, jwt_value = do_authentication(user_uuid)
    assert user.uuid == user_uuid


@pytest.mark.parametrize("default_organisation", ["default", "existing"])
@pytest.mark.django_db
def test_authentication_adds_user_to_default_organization(
    settings, default_organisation, organization
):
    """Configured default organization is set for users upon authentication."""
    user = UserFactory()
    settings.ENABLE_USER_DEFAULT_ORGANIZATION = True

    if default_organisation == "default":
        settings.USER_DEFAULT_ORGANIZATION_ID = DEFAULT_ORGANIZATION_ID
        expected_org_id = DEFAULT_ORGANIZATION_ID
    else:
        settings.USER_DEFAULT_ORGANIZATION_ID = organization.id
        expected_org_id = organization.id

    logged_user, jwt_value = do_authentication(user.uuid)

    assert logged_user.organization_memberships.count() == 1
    set_org = logged_user.organization_memberships.first()
    assert set_org.id == expected_org_id


@pytest.mark.django_db
def test_authentication_unset_default_organization(settings):
    """Default organization is not set for users, if the setting is empty."""
    settings.ENABLE_USER_DEFAULT_ORGANIZATION = True
    settings.USER_DEFAULT_ORGANIZATION_ID = ""
    user = UserFactory()

    logged_user, jwt_value = do_authentication(user.uuid)

    assert Organization.objects.filter(id=DEFAULT_ORGANIZATION_ID).count() == 0
    assert logged_user.organization_memberships.count() == 0


@pytest.mark.django_db
def test_authentication_default_organization_not_assigned_when_user_has_organization(
    settings, organization
):
    """Default organization is not set for users, which already have an organization."""
    settings.ENABLE_USER_DEFAULT_ORGANIZATION = True
    settings.USER_DEFAULT_ORGANIZATION_ID = DEFAULT_ORGANIZATION_ID
    user = UserFactory()
    user.organization_memberships.add(organization)

    logged_user, jwt_value = do_authentication(user.uuid)

    assert logged_user.organization_memberships.count() == 1
    set_org = logged_user.organization_memberships.first()
    assert set_org.id == organization.id


@pytest.mark.parametrize("enable_default", [True, False])
@pytest.mark.django_db
def test_authentication_default_organization_created_if_needed(
    enable_default, settings
):
    user = UserFactory()
    settings.ENABLE_USER_DEFAULT_ORGANIZATION = enable_default
    settings.USER_DEFAULT_ORGANIZATION_ID = DEFAULT_ORGANIZATION_ID

    # Default organization doesn't exist
    assert Organization.objects.filter(id=DEFAULT_ORGANIZATION_ID).count() == 0
    assert user.organization_memberships.count() == 0

    user, jwt_value = do_authentication(user.uuid)

    if enable_default:
        assert user.organization_memberships.count() == 1
        set_org = user.organization_memberships.first()
        assert set_org.id == DEFAULT_ORGANIZATION_ID
    else:
        assert Organization.objects.filter(id=DEFAULT_ORGANIZATION_ID).count() == 0
        assert user.organization_memberships.count() == 0
