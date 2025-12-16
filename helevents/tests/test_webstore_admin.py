import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from events.tests.factories import OrganizationFactory
from helevents.admin import WebStoreAccountInline, WebStoreMerchantInline
from registrations.models import WebStoreAccount, WebStoreMerchant


@pytest.fixture
def organization():
    return OrganizationFactory()


@pytest.fixture
def financial_admin_request(organization):
    user = get_user_model().objects.create(
        username="financial_admin",
        is_staff=True,
    )
    organization.financial_admin_users.add(user)
    req = RequestFactory().get("/")
    req.user = user
    return req


@pytest.fixture
def admin_request(organization):
    user = get_user_model().objects.create(
        username="admin",
        is_staff=True,
    )
    organization.admin_users.add(user)
    req = RequestFactory().get("/")
    req.user = user
    return req


@pytest.fixture
def merchant_inline():
    return WebStoreMerchantInline(WebStoreMerchant, AdminSite())


@pytest.fixture
def account_inline():
    return WebStoreAccountInline(WebStoreAccount, AdminSite())


@pytest.mark.django_db
def test_financial_admin_can_add_merchant(
    financial_admin_request, organization, merchant_inline
):
    assert (
        merchant_inline.has_add_permission(financial_admin_request, organization)
        is True
    )


@pytest.mark.django_db
def test_financial_admin_can_change_merchant(
    financial_admin_request, organization, merchant_inline
):
    assert (
        merchant_inline.has_change_permission(financial_admin_request, organization)
        is True
    )


@pytest.mark.django_db
def test_financial_admin_cannot_delete_merchant(
    financial_admin_request, organization, merchant_inline
):
    assert (
        merchant_inline.has_delete_permission(financial_admin_request, organization)
        is False
    )


@pytest.mark.django_db
def test_admin_only_cannot_add_merchant(admin_request, organization, merchant_inline):
    assert merchant_inline.has_add_permission(admin_request, organization) is False


@pytest.mark.django_db
def test_admin_only_cannot_change_merchant(
    admin_request, organization, merchant_inline
):
    assert merchant_inline.has_change_permission(admin_request, organization) is False


@pytest.mark.django_db
def test_financial_admin_can_add_account(
    financial_admin_request, organization, account_inline
):
    assert (
        account_inline.has_add_permission(financial_admin_request, organization) is True
    )


@pytest.mark.django_db
def test_financial_admin_can_change_account(
    financial_admin_request, organization, account_inline
):
    assert (
        account_inline.has_change_permission(financial_admin_request, organization)
        is True
    )


@pytest.mark.django_db
def test_financial_admin_cannot_delete_account(
    financial_admin_request, organization, account_inline
):
    assert (
        account_inline.has_delete_permission(financial_admin_request, organization)
        is False
    )


@pytest.mark.django_db
def test_admin_only_cannot_add_account(admin_request, organization, account_inline):
    assert account_inline.has_add_permission(admin_request, organization) is False


@pytest.mark.django_db
def test_admin_only_cannot_change_account(admin_request, organization, account_inline):
    assert account_inline.has_change_permission(admin_request, organization) is False
