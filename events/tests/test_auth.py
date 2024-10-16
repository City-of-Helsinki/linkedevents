import uuid
from unittest.mock import PropertyMock, patch

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
from .factories import OrganizationFactory
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
    request = rf.get("/path", headers={"authorization": auth_header})

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

    def test_is_registration_admin(self):
        self.user.registration_admin_organizations.add(self.org_1)

        is_admin = self.user.is_registration_admin_of(self.org_1)
        self.assertFalse(is_admin)

        self.data_source.user_editable_registrations = True
        self.data_source.save(update_fields=["user_editable_registrations"])

        is_admin = self.user.is_registration_admin_of(self.org_1)
        self.assertTrue(is_admin)

        is_admin = self.user.is_registration_admin_of(self.org_2)
        self.assertFalse(is_admin)

    def test_is_financial_admin(self):
        self.user.financial_admin_organizations.add(self.org_1)

        is_admin = self.user.is_financial_admin_of(self.org_1)
        self.assertFalse(is_admin)

        self.data_source.user_editable_registration_price_groups = True
        self.data_source.save(update_fields=["user_editable_registration_price_groups"])

        is_admin = self.user.is_financial_admin_of(self.org_1)
        self.assertTrue(is_admin)

        is_admin = self.user.is_financial_admin_of(self.org_2)
        self.assertFalse(is_admin)

    def test_is_regular_user(self):
        is_regular_user = self.user.is_regular_user_of(self.org_1)
        self.assertFalse(is_regular_user)

        is_regular_user = self.user.is_regular_user_of(self.org_2)
        self.assertFalse(is_regular_user)

    def test_is_external(self):
        is_external = self.user.is_external
        self.assertFalse(is_external)

    def test_get_financial_admin_organizations_and_descendants(self):
        child_org = OrganizationFactory(
            name="child-org",
            origin_id="child-org",
            data_source=self.data_source,
            parent=self.org_1,
        )

        self.user.financial_admin_organizations.add(self.org_1)

        assert (
            len(
                self.user.get_financial_admin_organizations_and_descendants().values_list(
                    "pk", flat=True
                )
            )
            == 0
        )

        self.data_source.user_editable_registration_price_groups = True
        self.data_source.save(update_fields=["user_editable_registration_price_groups"])

        assert set(
            self.user.get_financial_admin_organizations_and_descendants().values_list(
                "pk", flat=True
            )
        ) == {self.org_1.pk, child_org.pk}


@pytest.mark.django_db
def test_valid_jwt_is_accepted():
    """JWT generated in tests has a valid signature and is accepted."""
    user_uuid = uuid.UUID("b7a35517-eb1f-46c9-88bf-3206fb659c3c")
    user, jwt_value = do_authentication(user_uuid)
    assert user.uuid == user_uuid


@pytest.mark.parametrize(
    "login_method,expected",
    [
        pytest.param(["keycloak-internal"], False, id="list-amr"),
        pytest.param("tunnistamo-internal", False, id="plain-amr"),
        pytest.param("non-ad-method", True, id="external-method-plain"),
        pytest.param(["non-ad-method"], True, id="external-method-list"),
        pytest.param([], True, id="empty"),
    ],
)
@pytest.mark.django_db
def test_user_is_external_based_on_login_method(
    api_client, settings, login_method, expected
):
    """Using AD authentication forces the User.is_external to False."""
    settings.NON_EXTERNAL_AUTHENTICATION_METHODS = [
        "keycloak-internal",
        "tunnistamo-internal",
    ]
    user = UserFactory()
    detail_url = versioned_reverse("user-detail", kwargs={"pk": user.uuid})
    auth_header = get_api_token_for_user_with_scopes(
        user.uuid,
        [api_token_auth_settings.API_SCOPE_PREFIX],
        req_mock,
        amr=login_method,
    )
    api_client.credentials(HTTP_AUTHORIZATION=auth_header)

    response = api_client.get(detail_url, format="json")

    assert response.status_code == status.HTTP_200_OK, str(response.content)
    assert response.data["is_external"] == expected


@pytest.mark.parametrize(
    "login_method,expected",
    [
        pytest.param(["strong"], True, id="strong"),
        pytest.param(["not-strong"], False, id="not-strong"),
        pytest.param([], False, id="empty"),
    ],
)
@pytest.mark.django_db
def test_user_is_strongly_identified(user, settings, login_method, expected):
    settings.STRONG_IDENTIFICATION_AUTHENTICATION_METHODS = ["strong"]

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=login_method,
    ) as mocked:
        assert user.is_strongly_identified == expected
        assert mocked.called is True


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
