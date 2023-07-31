import datetime
import uuid

import pytest
from django.test import RequestFactory, TestCase
from django_orghierarchy.models import Organization
from helusers.oidc import ApiTokenAuthentication
from helusers.settings import api_token_auth_settings
from jose import jwt
from rest_framework import status

from events.models import DataSource
from helevents.tests.factories import UserFactory

from ..auth import ApiKeyUser
from .keys import rsa_key
from .utils import versioned_reverse

DEFAULT_ORGANIZATION_ID = "others"

req_mock = None


@pytest.fixture(autouse=True)
def global_requests_mock(requests_mock):
    global req_mock
    req_mock = requests_mock
    yield requests_mock

    req_mock = None


def get_api_token_for_user_with_scopes(user_uuid, scopes: list, amr: str = None):
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
        "amr": amr if amr else "github",
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
    auth = ApiTokenAuthentication()

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
        is_admin = self.user.is_admin_of(self.org_1)
        self.assertTrue(is_admin)

        is_admin = self.user.is_admin_of(self.org_2)
        self.assertFalse(is_admin)

    def test_is_regular_user(self):
        is_regular_user = self.user.is_regular_user_of(self.org_1)
        self.assertFalse(is_regular_user)

        is_regular_user = self.user.is_regular_user_of(self.org_2)
        self.assertFalse(is_regular_user)


@pytest.mark.django_db
def test_valid_jwt_is_accepted():
    """JWT generated in tests has a valid signature and is accepted."""
    user_uuid = uuid.UUID("b7a35517-eb1f-46c9-88bf-3206fb659c3c")
    user, jwt_value = do_authentication(user_uuid)
    assert user.uuid == user_uuid


@pytest.mark.parametrize("login_using_ad", [True, False])
@pytest.mark.django_db
def test_user_is_external_based_on_login_method(api_client, settings, login_using_ad):
    """Using AD authentication forces the User.is_external to False."""
    user = UserFactory()
    detail_url = versioned_reverse("user-detail", kwargs={"pk": user.uuid})
    ad_method = "helsinkiazuread"
    settings.NON_EXTERNAL_AUTHENTICATION_METHODS = [ad_method]
    if login_using_ad:
        auth_method = ad_method
    else:
        auth_method = "non-ad_method"
    auth_header = get_api_token_for_user_with_scopes(
        user.uuid, [api_token_auth_settings.API_SCOPE_PREFIX], amr=auth_method
    )
    api_client.credentials(HTTP_AUTHORIZATION=auth_header)

    response = api_client.get(detail_url, format="json")

    assert response.status_code == status.HTTP_200_OK, str(response.content)
    assert response.data["is_external"] != login_using_ad
