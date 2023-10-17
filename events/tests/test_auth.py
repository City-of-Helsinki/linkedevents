import uuid

import pytest
from django.test import RequestFactory, TestCase
from django_orghierarchy.models import Organization
from helusers.oidc import ApiTokenAuthentication
from helusers.settings import api_token_auth_settings
from rest_framework import status

from events.models import DataSource
from helevents.tests.conftest import get_api_token_for_user_with_scopes
from helevents.tests.factories import UserFactory

from ..auth import ApiKeyUser
from .utils import versioned_reverse

DEFAULT_ORGANIZATION_ID = "others"

req_mock = None


@pytest.fixture(autouse=True)
def global_requests_mock(requests_mock):
    global req_mock
    req_mock = requests_mock
    yield requests_mock

    req_mock = None


def do_authentication(user_uuid):
    auth = ApiTokenAuthentication()

    auth_header = get_api_token_for_user_with_scopes(
        user_uuid, [api_token_auth_settings.API_SCOPE_PREFIX], req_mock
    )

    rf = RequestFactory()
    request = rf.get("/path", HTTP_AUTHORIZATION=auth_header)

    return auth.authenticate(request)


@pytest.mark.no_use_audit_log
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

    def test_is_external(self):
        is_external = self.user.is_external
        self.assertFalse(is_external)


@pytest.mark.no_use_audit_log
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
        user.uuid, [api_token_auth_settings.API_SCOPE_PREFIX], req_mock, amr=auth_method
    )
    api_client.credentials(HTTP_AUTHORIZATION=auth_header)

    response = api_client.get(detail_url, format="json")

    assert response.status_code == status.HTTP_200_OK, str(response.content)
    assert response.data["is_external"] != login_using_ad


@pytest.mark.parametrize("authenticated", [True, False])
@pytest.mark.django_db
def test_authenticated_requests_add_no_cache_headers(api_client, authenticated):
    """Authenticated requests should indicate that responses shouldn't be cached."""
    if authenticated:
        user = UserFactory()
        auth_header = get_api_token_for_user_with_scopes(
            user.uuid, [api_token_auth_settings.API_SCOPE_PREFIX], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)
    detail_url = versioned_reverse("event-list")

    response = api_client.get(detail_url, format="json")

    assert response.status_code == status.HTTP_200_OK
    cache_controls = {
        v.lower().strip() for v in response.get("Cache-Control", "").split(",")
    }
    if authenticated:
        assert cache_controls == {
            "max-age=0",
            "no-cache",
            "no-store",
            "must-revalidate",
            "private",
        }
    else:
        # Sanity check for the opposite case
        assert cache_controls == {""}
