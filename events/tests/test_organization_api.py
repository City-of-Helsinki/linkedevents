import pytest
import requests_mock
from django.conf import settings as django_settings
from django.test import override_settings
from django.utils import translation
from django_orghierarchy.models import Organization
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.api import OrganizationDetailSerializer
from events.tests.utils import assert_fields_exist
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import WebStoreAccount, WebStoreMerchant
from registrations.tests.factories import (
    WebStoreAccountFactory,
    WebStoreMerchantFactory,
)
from registrations.tests.utils import create_user_by_role
from web_store.tests.merchant.test_web_store_merchant_api_client import (
    DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
    DEFAULT_MERCHANT_ID,
)

organization_name = "test org"
edited_organization_name = "new name"
default_web_store_merchants_data = [
    {
        "active": True,
        "name": "Test Merchant",
        "street_address": "Street Address",
        "zipcode": "12345",
        "city": "Test City",
        "email": "test@test.dev",
        "phone_number": "+3580000000",
        "terms_of_service_url": "https://test.dev/terms_of_service/",
        "business_id": "1234567-8",
        "paytrail_merchant_id": "1234567",
    }
]
default_web_store_accounts_data = [
    {
        "active": True,
        "name": "Test Account",
        "company_code": "1234",
        "main_ledger_account": "123456",
        "balance_profit_center": "1234567890",
    }
]
merchant_create_url = (
    f"{django_settings.WEB_STORE_API_BASE_URL}merchant/create/"
    f"merchant/{django_settings.WEB_STORE_API_NAMESPACE}"
)


def organization_id(pk):
    obj_id = reverse(OrganizationDetailSerializer.view_name, kwargs={"pk": pk})
    return obj_id


def get_organization(api_client, pk):
    url = reverse(OrganizationDetailSerializer.view_name, kwargs={"pk": pk})

    response = api_client.get(url, format="json")
    return response


def get_organization_merchants(api_client, pk):
    base_url = reverse(OrganizationDetailSerializer.view_name, kwargs={"pk": pk})
    url = f"{base_url}merchants/"

    response = api_client.get(url, format="json")
    return response


def get_organization_accounts(api_client, pk):
    base_url = reverse(OrganizationDetailSerializer.view_name, kwargs={"pk": pk})
    url = f"{base_url}accounts/"

    response = api_client.get(url, format="json")
    return response


def create_organization(api_client, organization_data):
    url = reverse("organization-list")

    response = api_client.post(url, organization_data, format="json")
    return response


def assert_create_organization(api_client, organization_data):
    response = create_organization(api_client, organization_data)

    assert response.status_code == status.HTTP_201_CREATED
    return response


def delete_organization(api_client, pk):
    url = reverse(OrganizationDetailSerializer.view_name, kwargs={"pk": pk})

    response = api_client.delete(url)
    return response


def assert_delete_organization(api_client, pk):
    response = delete_organization(api_client, pk)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    return response


def update_organization(api_client, pk, organization_data):
    url = reverse(OrganizationDetailSerializer.view_name, kwargs={"pk": pk})

    response = api_client.put(url, organization_data, format="json")
    return response


def assert_update_organization(api_client, pk, organization_data):
    response = update_organization(api_client, pk, organization_data)
    assert response.status_code == status.HTTP_200_OK
    return response


def patch_organization(api_client, pk, organization_data):
    url = reverse(OrganizationDetailSerializer.view_name, kwargs={"pk": pk})

    response = api_client.patch(url, organization_data, format="json")
    return response


def assert_patch_organization(api_client, pk, organization_data):
    response = patch_organization(api_client, pk, organization_data)
    assert response.status_code == status.HTTP_200_OK
    return response


def assert_merchant_fields_exist(data, is_admin_user=False):
    fields = (
        "id",
        "active",
        "name",
        "street_address",
        "zipcode",
        "city",
        "email",
        "phone_number",
        "url",
        "terms_of_service_url",
        "business_id",
        "created_by",
        "created_time",
        "last_modified_by",
        "last_modified_time",
    )

    if is_admin_user:
        fields += (
            "paytrail_merchant_id",
            "merchant_id",
        )

    assert_fields_exist(data, fields)


def assert_account_fields_exist(data):
    fields = (
        "id",
        "active",
        "name",
        "company_code",
        "main_ledger_account",
        "balance_profit_center",
        "internal_order",
        "profit_center",
        "project",
        "operation_area",
        "created_by",
        "created_time",
        "last_modified_by",
        "last_modified_time",
    )

    assert_fields_exist(data, fields)


@pytest.mark.django_db
def test_admin_user_can_see_organization_users(organization, user, user_api_client):
    organization.regular_users.add(user)

    response = get_organization(user_api_client, organization.id)
    assert response.data["admin_users"]
    assert response.data["regular_users"]


@pytest.mark.django_db
def test_anonymous_user_cannot_see_organization_users(api_client, organization, user):
    organization.regular_users.add(user)

    response = get_organization(api_client, organization.id)
    assert response.data.get("admin_users") is None
    assert response.data.get("regular_users") is None


@pytest.mark.django_db
def test_regular_user_cannot_see_organization_users(
    organization, user, user_api_client
):
    organization.regular_users.add(user)
    organization.admin_users.remove(user)

    response = get_organization(user_api_client, organization.id)
    assert response.data.get("admin_users") is None
    assert response.data.get("regular_users") is None


@pytest.mark.django_db
def test_admin_user_can_create_organization(data_source, organization, user_api_client):
    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
    }

    response = assert_create_organization(user_api_client, payload)
    assert response.data["name"] == payload["name"]


@pytest.mark.django_db
def test_organization_id_is_audit_logged_on_post(
    data_source, organization, user_api_client
):
    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
    }

    response = assert_create_organization(user_api_client, payload)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data["id"]
    ]


@pytest.mark.django_db
def test_cannot_create_organization_with_existing_id(organization, user_api_client):
    payload = {
        "data_source": organization.data_source.id,
        "origin_id": organization.origin_id,
        "id": organization.id,
        "name": organization_name,
    }

    response = create_organization(user_api_client, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["non_field_errors"][0].code == "unique"


@pytest.mark.django_db
def test_admin_user_can_create_organization_with_parent(
    data_source, organization, user_api_client
):
    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "parent_organization": organization_id(organization.pk),
    }

    response = assert_create_organization(user_api_client, payload)
    assert response.data["parent_organization"] == payload["parent_organization"]


@pytest.mark.django_db
def test_cannot_create_organization_with_parent_user_has_no_rights(
    api_client, data_source, organization, organization2, user2
):
    api_client.force_authenticate(user2)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "parent_organization": organization_id(organization.pk),
    }

    with translation.override("en"):
        response = create_organization(api_client, payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert str(response.data["detail"]) == "User has no rights to this organization"


@pytest.mark.django_db
def test_create_organization_with_sub_organizations(
    data_source, organization, organization2, user_api_client
):
    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "sub_organizations": [
            organization_id(organization.id),
            organization_id(organization2.id),
        ],
    }

    response = assert_create_organization(user_api_client, payload)
    org_id = response.data["id"]
    response = get_organization(user_api_client, org_id)
    assert set(response.data["sub_organizations"]) == set(payload["sub_organizations"])


@pytest.mark.django_db
def test_cannot_add_sub_organization_with_wrong_id(
    data_source, organization, organization2, user_api_client
):
    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "sub_organizations": ["wrong.id", organization_id(organization2.id)],
    }

    response = assert_create_organization(user_api_client, payload)
    org_id = response.data["id"]
    response = get_organization(user_api_client, org_id)
    assert set(response.data["sub_organizations"]) == set(
        [organization_id(organization2.id)]
    )


@pytest.mark.django_db
def test_create_organization_with_affiliated_organizations(
    data_source, organization, organization2, user_api_client
):
    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "affiliated_organizations": [
            organization_id(organization.id),
            organization_id(organization2.id),
        ],
    }

    for i in [organization, organization2]:
        i.internal_type = Organization.AFFILIATED
        i.save()

    response = assert_create_organization(user_api_client, payload)
    org_id = response.data["id"]
    response = get_organization(user_api_client, org_id)
    assert set(response.data["affiliated_organizations"]) == set(
        payload["affiliated_organizations"]
    )


@pytest.mark.django_db
def test_user_is_automatically_added_to_admins_users(
    api_client, organization, data_source, user, user_api_client
):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)
    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
    }

    response = assert_create_organization(user_api_client, payload)
    assert response.data["admin_users"][0]["username"] == user.username


@pytest.mark.django_db
def test_admin_user_add_users_to_new_organization(
    api_client, organization, data_source, user, user2, user_api_client
):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)
    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "admin_users": [user.username, user2.username],
        "regular_users": [user2.username],
    }

    response = assert_create_organization(user_api_client, payload)
    assert set(payload["admin_users"]) == set(
        [i["username"] for i in response.data["admin_users"]]
    )
    assert set(payload["regular_users"]) == set(
        [i["username"] for i in response.data["regular_users"]]
    )


@pytest.mark.django_db
def test_admin_user_add_registration_admin_users_to_new_organization(
    api_client, organization, data_source, user, user2, user_api_client
):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)
    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "admin_users": [user.username, user2.username],
        "registration_admin_users": [user2.username],
    }
    admins_set = set(payload["admin_users"])
    registration_admins_set = set(payload["registration_admin_users"])

    response = assert_create_organization(user_api_client, payload)
    assert admins_set == set([i["username"] for i in response.data["admin_users"]])
    assert registration_admins_set == set(
        [i["username"] for i in response.data["registration_admin_users"]]
    )
    new_organization = Organization.objects.get(id=f"{data_source.id}:{origin_id}")
    assert admins_set == set(
        new_organization.admin_users.values_list("username", flat=True)
    )
    assert registration_admins_set == set(
        new_organization.registration_admin_users.values_list("username", flat=True)
    )


@pytest.mark.django_db
def test_admin_user_add_financial_admin_users_to_new_organization(
    api_client, organization, data_source, user2
):
    user = UserFactory()
    user.admin_organizations.add(organization)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "financial_admin_users": [user2.username],
    }
    financial_admins_set = set(payload["financial_admin_users"])

    response = assert_create_organization(api_client, payload)
    assert financial_admins_set == set(
        [i["username"] for i in response.data["financial_admin_users"]]
    )
    new_organization = Organization.objects.get(id=f"{data_source.id}:{origin_id}")
    assert financial_admins_set == set(
        new_organization.financial_admin_users.values_list("username", flat=True)
    )


@pytest.mark.django_db
def test_admin_user_can_update_organization(organization, user_api_client):
    payload = {
        "id": organization.id,
        "name": edited_organization_name,
    }

    response = assert_update_organization(user_api_client, organization.id, payload)
    assert response.data["name"] == payload["name"]


@pytest.mark.django_db
def test_organization_id_is_audit_logged_on_put(organization, user_api_client):
    payload = {
        "id": organization.id,
        "name": edited_organization_name,
    }

    assert_update_organization(user_api_client, organization.pk, payload)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        organization.pk
    ]


@pytest.mark.django_db
def test_admin_user_update_organization_registration_admin_users(
    organization, user2, user_api_client
):
    assert organization.registration_admin_users.count() == 0

    payload = {
        "id": organization.id,
        "name": organization_name,
        "registration_admin_users": [user2.username],
    }

    response = assert_update_organization(user_api_client, organization.id, payload)
    assert set(payload["registration_admin_users"]) == set(
        [i["username"] for i in response.data["registration_admin_users"]]
    )

    organization.refresh_from_db()
    assert organization.registration_admin_users.count() == 1


@pytest.mark.django_db
def test_admin_user_update_organization_financial_admin_users(
    organization, user2, user_api_client
):
    assert organization.financial_admin_users.count() == 0

    payload = {
        "id": organization.id,
        "name": organization_name,
        "financial_admin_users": [user2.username],
    }

    response = assert_update_organization(user_api_client, organization.id, payload)
    assert set(payload["financial_admin_users"]) == set(
        [i["username"] for i in response.data["financial_admin_users"]]
    )

    organization.refresh_from_db()
    assert organization.financial_admin_users.count() == 1


@pytest.mark.django_db
def test_anonymous_user_cannot_update_organization(api_client, organization):
    payload = {
        "id": organization.id,
        "name": edited_organization_name,
    }

    response = update_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_regular_user_cannot_update_organization(organization, user, user_api_client):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    payload = {
        "id": organization.id,
        "name": edited_organization_name,
    }

    response = update_organization(user_api_client, organization.id, payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_user_from_other_organization_cannot_update_organization(
    api_client, organization, user, user2
):
    api_client.force_authenticate(user2)

    payload = {
        "id": organization.id,
        "name": edited_organization_name,
    }

    response = update_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_user_can_edit_users(
    organization, super_user, user, user2, user_api_client
):
    organization.admin_users.add(super_user)

    payload = {
        "id": organization.id,
        "name": organization.name,
        "admin_users": [user.username, user2.username],
        "regular_users": [user2.username],
    }

    response = assert_update_organization(user_api_client, organization.pk, payload)
    assert set(payload["admin_users"]) == set(
        [i["username"] for i in response.data["admin_users"]]
    )
    assert set(payload["regular_users"]) == set(
        [i["username"] for i in response.data["regular_users"]]
    )


@pytest.mark.django_db
def test_user_cannot_remove_itself_from_admins(organization, user, user_api_client):
    payload = {"id": organization.id, "name": organization.name, "admin_users": []}

    response = assert_update_organization(user_api_client, organization.pk, payload)
    assert response.data["admin_users"][0]["username"] == user.username


@pytest.mark.django_db
def test_admin_user_can_delete_organization(organization, user_api_client):
    assert_delete_organization(user_api_client, organization.id)
    response = get_organization(user_api_client, organization.id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_organization_id_is_audit_logged_on_delete(organization, user_api_client):
    assert_delete_organization(user_api_client, organization.pk)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        organization.pk
    ]


@pytest.mark.django_db
def test_anonymous_user_can_delete_organization(api_client, organization):
    response = delete_organization(api_client, organization.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_regular_user_cannot_delete_organization(organization, user, user_api_client):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    response = delete_organization(user_api_client, organization.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_admin_user_from_other_organization_cannot_delete_organization(
    api_client, organization, user, user2
):
    api_client.force_authenticate(user2)

    response = delete_organization(api_client, organization.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    "user2_with_user_type, expected_status",
    [
        (None, status.HTTP_403_FORBIDDEN),
        ("org_regular", status.HTTP_403_FORBIDDEN),
        ("org_admin", status.HTTP_201_CREATED),
        ("staff", status.HTTP_403_FORBIDDEN),
        ("admin", status.HTTP_403_FORBIDDEN),
        ("superuser", status.HTTP_201_CREATED),
    ],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_permissions_create_organization(
    api_client, data_source, user2_with_user_type, expected_status
):
    api_client.force_authenticate(user2_with_user_type)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
    }
    response = create_organization(api_client, payload)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "user2_with_user_type, expected_status",
    [
        (None, status.HTTP_403_FORBIDDEN),
        ("org_regular", status.HTTP_403_FORBIDDEN),
        ("org_admin", status.HTTP_200_OK),
        ("staff", status.HTTP_403_FORBIDDEN),
        ("admin", status.HTTP_403_FORBIDDEN),
        ("superuser", status.HTTP_200_OK),
    ],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_permissions_update_organization(
    api_client, organization, user2_with_user_type, expected_status
):
    api_client.force_authenticate(user2_with_user_type)

    payload = {
        "data_source": organization.data_source.pk,
        "name": "New name",
    }
    response = update_organization(api_client, organization.pk, payload)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "user2_with_user_type, expected_status",
    [
        (None, status.HTTP_403_FORBIDDEN),
        ("org_regular", status.HTTP_403_FORBIDDEN),
        ("org_admin", status.HTTP_204_NO_CONTENT),
        ("staff", status.HTTP_403_FORBIDDEN),
        ("admin", status.HTTP_403_FORBIDDEN),
        ("superuser", status.HTTP_204_NO_CONTENT),
    ],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_permissions_destroy_organization(
    api_client, organization, user2_with_user_type, expected_status
):
    api_client.force_authenticate(user2_with_user_type)
    response = delete_organization(api_client, organization.pk)
    assert response.status_code == expected_status


@pytest.mark.django_db
def test_get_organization_list_html_renders(api_client, event):
    url = reverse("organization-list", version="v1")
    response = api_client.get(url, data=None, headers={"accept": "text/html"})
    assert response.status_code == status.HTTP_200_OK, str(response.content)


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_superuser_or_financial_and_event_admin_can_create_organization_with_web_store_merchant(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    if user_role == "financial_admin":
        user.admin_organizations.add(organization)

    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": default_web_store_merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            merchant_create_url, json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA
        )

        response = assert_create_organization(api_client, payload)

        assert req_mock.call_count == 1

    assert len(response.data["web_store_merchants"]) == 1
    assert (
        response.data["web_store_merchants"][0]["url"]
        == django_settings.LINKED_EVENTS_UI_URL
    )

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=response.data["id"],
            merchant_id=response.data["web_store_merchants"][0]["merchant_id"],
            url=django_settings.LINKED_EVENTS_UI_URL,
            created_by=user,
            last_modified_by=user,
            created_time__isnull=False,
            last_modified_time__isnull=False,
            **payload["web_store_merchants"][0],
        ).count()
        == 1
    )


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_superuser_or_financial_and_event_admin_can_update_organization_with_web_store_merchant(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    if user_role == "financial_admin":
        user.admin_organizations.add(organization)

    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": default_web_store_merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            merchant_create_url, json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA
        )

        response = assert_update_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 1

    assert len(response.data["web_store_merchants"]) == 1
    assert (
        response.data["web_store_merchants"][0]["url"]
        == django_settings.LINKED_EVENTS_UI_URL
    )

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=response.data["id"],
            merchant_id=response.data["web_store_merchants"][0]["merchant_id"],
            url=django_settings.LINKED_EVENTS_UI_URL,
            created_by=user,
            last_modified_by=user,
            created_time__isnull=False,
            last_modified_time__isnull=False,
            **payload["web_store_merchants"][0],
        ).count()
        == 1
    )


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_superuser_and_financial_admin_can_patch_organization_with_web_store_merchant(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    payload = {
        "web_store_merchants": default_web_store_merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            merchant_create_url, json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA
        )

        response = assert_patch_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 1

    assert len(response.data["web_store_merchants"]) == 1
    assert (
        response.data["web_store_merchants"][0]["url"]
        == django_settings.LINKED_EVENTS_UI_URL
    )

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=response.data["id"],
            merchant_id=response.data["web_store_merchants"][0]["merchant_id"],
            url=django_settings.LINKED_EVENTS_UI_URL,
            created_by=user,
            last_modified_by=user,
            created_time__isnull=False,
            last_modified_time__isnull=False,
            **payload["web_store_merchants"][0],
        ).count()
        == 1
    )


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_superuser_and_financial_can_patch_organizations_web_store_merchant(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(
            organization=organization,
            merchant_id="1234",
            paytrail_merchant_id=default_web_store_merchants_data[0][
                "paytrail_merchant_id"
            ],
        )

    merchants_data = default_web_store_merchants_data[0].copy()
    merchants_data["id"] = merchant.pk
    payload = {
        "web_store_merchants": [merchants_data],
    }

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=organization.id,
            url=django_settings.LINKED_EVENTS_UI_URL,
            **payload["web_store_merchants"][0],
        ).count()
        == 0
    )
    assert merchant.last_modified_by is None
    last_modified_time = merchant.last_modified_time

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/update/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}",
            json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
        )

        response = assert_patch_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 1

    assert len(response.data["web_store_merchants"]) == 1
    assert (
        response.data["web_store_merchants"][0]["url"]
        == django_settings.LINKED_EVENTS_UI_URL
    )

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=organization.id,
            url=django_settings.LINKED_EVENTS_UI_URL,
            **payload["web_store_merchants"][0],
        ).count()
        == 1
    )
    merchant.refresh_from_db()
    assert merchant.last_modified_by == user
    assert merchant.last_modified_time > last_modified_time


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin", "admin"])
@pytest.mark.django_db
def test_new_web_store_merchant_created_if_paytrail_merchant_id_changed(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    if user_role == "admin":
        user.financial_admin_organizations.add(organization)
    elif user_role == "financial_admin":
        user.admin_organizations.add(organization)

    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(
            organization=organization, merchant_id="1234"
        )

    new_merchant_id = "9876"
    new_paytrail_merchant_id = "4321"

    merchants_data = default_web_store_merchants_data[0].copy()
    merchants_data["id"] = merchant.pk
    merchants_data["paytrail_merchant_id"] = new_paytrail_merchant_id

    payload = {
        "data_source": data_source.id,
        "origin_id": organization.origin_id,
        "id": f"{data_source.id}:{organization.origin_id}",
        "name": organization_name,
        "web_store_merchants": [merchants_data],
    }

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=organization.id,
            merchant_id=new_merchant_id,
            **merchants_data,
        ).count()
        == 0
    )

    json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
    json_return_value["merchantId"] = new_merchant_id
    with requests_mock.Mocker() as req_mock:
        req_mock.post(merchant_create_url, json=json_return_value)

        response = assert_update_organization(api_client, organization.id, payload)
        assert len(response.data["web_store_merchants"]) == 1

        assert req_mock.call_count == 1

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=organization.id,
            merchant_id=new_merchant_id,
            **merchants_data,
        ).count()
        == 1
    )


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_superuser_and_financial_can_make_web_store_merchant_inactive(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(
            organization=organization, merchant_id="1234"
        )

    payload = {
        "web_store_merchants": [
            {
                "id": merchant.pk,
                "active": False,
            }
        ],
    }

    assert WebStoreMerchant.objects.count() == 1
    assert merchant.active is True
    assert merchant.last_modified_by is None
    last_modified_time = merchant.last_modified_time

    with requests_mock.Mocker() as req_mock:
        req_mock.post(merchant_create_url)
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/update/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}"
        )

        response = assert_patch_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 0

    assert len(response.data["web_store_merchants"]) == 1

    merchant.refresh_from_db()
    assert WebStoreMerchant.objects.count() == 1
    assert merchant.active is False
    assert merchant.last_modified_by == user
    assert merchant.last_modified_time > last_modified_time


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_cannot_post_web_store_merchant_id_or_url(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    if user_role == "financial_admin":
        user.admin_organizations.add(organization)

    api_client.force_authenticate(user)

    origin_id = "test_organization2"

    web_store_merchant_data = default_web_store_merchants_data[0].copy()
    web_store_merchant_data.update(
        {
            "merchant_id": "4321",
            "url": "http://www.homepage.dev/",
        }
    )
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": [web_store_merchant_data],
    }

    assert WebStoreMerchant.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            merchant_create_url, json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA
        )

        response = assert_create_organization(api_client, payload)

        assert req_mock.call_count == 1

    assert len(response.data["web_store_merchants"]) == 1

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=response.data["id"],
            merchant_id=DEFAULT_MERCHANT_ID,
            url=django_settings.LINKED_EVENTS_UI_URL,
        ).count()
        == 1
    )


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_cannot_put_web_store_merchant_id_or_url(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    if user_role == "financial_admin":
        user.admin_organizations.add(organization)

    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    original_merchant_id = "1234"

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(
            organization=organization, merchant_id=original_merchant_id
        )

    web_store_merchant_data = default_web_store_merchants_data[0].copy()
    web_store_merchant_data.update(
        {
            "id": merchant.pk,
            "merchant_id": "4321",
            "url": "http://www.homepage.dev/",
            "paytrail_merchant_id": merchant.paytrail_merchant_id,
        }
    )
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": [web_store_merchant_data],
    }

    assert WebStoreMerchant.objects.count() == 1

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/update/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}",
            json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
        )

        assert_update_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 1

    assert WebStoreMerchant.objects.count() == 1

    merchant.refresh_from_db()
    assert merchant.merchant_id == original_merchant_id
    assert merchant.url == django_settings.LINKED_EVENTS_UI_URL


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_cannot_patch_web_store_merchant_id_or_url(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    original_merchant_id = "1234"

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(
            organization=organization, merchant_id=original_merchant_id
        )

    payload = {
        "web_store_merchants": [
            {
                "id": merchant.pk,
                "merchant_id": "4321",
                "url": "http://www.homepage.dev/",
                "name": "Edited merchant name",
            }
        ],
    }

    assert WebStoreMerchant.objects.count() == 1
    assert merchant.merchant_id == original_merchant_id

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/update/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}",
            json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
        )

        assert_patch_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 1

    assert WebStoreMerchant.objects.count() == 1

    merchant.refresh_from_db()
    assert merchant.merchant_id == original_merchant_id
    assert merchant.url == django_settings.LINKED_EVENTS_UI_URL


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "financial_admin",
        "registration_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_create_an_organization_with_a_web_store_merchant(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": default_web_store_merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.post(merchant_create_url)

        response = create_organization(api_client, payload)

        assert req_mock.call_count == 0

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_merchants") is None

    assert WebStoreMerchant.objects.count() == 0


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "financial_admin",
        "registration_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_update_an_organization_with_a_web_store_merchant(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": default_web_store_merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.post(merchant_create_url)

        response = update_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 0

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_merchants") is None

    assert WebStoreMerchant.objects.count() == 0


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "financial_admin",
        "registration_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_update_an_organizations_web_store_merchant(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(
            organization=organization, merchant_id="1234"
        )

    origin_id = "test_organization2"

    merchants_data = default_web_store_merchants_data[0].copy()
    merchants_data["id"] = merchant.pk

    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": [merchants_data],
    }

    assert WebStoreMerchant.objects.count() == 1

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/update/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}",
        )
        req_mock.post(merchant_create_url)

        response = update_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 0

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_merchants") is None

    assert WebStoreMerchant.objects.count() == 1


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "registration_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_patch_an_organizations_web_store_merchant(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(
            organization=organization, merchant_id="1234"
        )

    merchants_data = default_web_store_merchants_data[0].copy()
    merchants_data["id"] = merchant.pk
    payload = {
        "web_store_merchants": [merchants_data],
    }

    assert WebStoreMerchant.objects.count() == 1

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/update/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}",
        )
        req_mock.post(merchant_create_url)

        response = patch_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 0

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_merchants") is None
    assert WebStoreMerchant.objects.count() == 1


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin", "admin"])
@pytest.mark.django_db
def test_superuser_and_financial_admin_can_get_organization_with_all_web_store_merchant_fields(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    if user_role == "admin":
        user.financial_admin_organizations.add(organization)

    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        WebStoreMerchantFactory(organization=organization, merchant_id="1234")

    response = get_organization(api_client, organization.id)
    assert response.status_code == status.HTTP_200_OK
    assert_merchant_fields_exist(
        response.data["web_store_merchants"][0], is_admin_user=True
    )


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "registration_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_get_organization_with_all_web_store_merchant_fields(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        WebStoreMerchantFactory(organization=organization, merchant_id="1234")

    response = get_organization(api_client, organization.id)
    assert response.status_code == status.HTTP_200_OK
    assert_merchant_fields_exist(response.data["web_store_merchants"][0])


@pytest.mark.django_db
def test_can_create_organization_with_more_than_one_web_store_merchant(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"

    merchant_data = default_web_store_merchants_data[0].copy()
    merchant_data2 = {
        "active": True,
        "name": "Test Merchant 2",
        "street_address": "Street Address 2",
        "zipcode": "12345",
        "city": "Test City",
        "email": "test2@test.dev",
        "phone_number": "+3580000001",
        "terms_of_service_url": "https://test2.dev/terms_of_service/",
        "business_id": "1234567-9",
        "paytrail_merchant_id": "12345678",
    }

    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": [merchant_data, merchant_data2],
    }

    assert WebStoreMerchant.objects.count() == 0

    json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
    json_return_value["merchantId"] = "1234"
    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            merchant_create_url,
            json=json_return_value,
        )

        assert_create_organization(api_client, payload)

        assert req_mock.call_count == 2

    assert WebStoreMerchant.objects.count() == 2


@pytest.mark.django_db
def test_can_update_organization_with_more_than_one_web_store_merchant(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"

    merchant_data = default_web_store_merchants_data[0].copy()
    merchant_data2 = {
        "active": True,
        "name": "Test Merchant 2",
        "street_address": "Street Address 2",
        "zipcode": "12345",
        "city": "Test City",
        "email": "test2@test.dev",
        "phone_number": "+3580000001",
        "terms_of_service_url": "https://test2.dev/terms_of_service/",
        "business_id": "1234567-9",
        "paytrail_merchant_id": "12345678",
    }

    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": [merchant_data, merchant_data2],
    }

    assert WebStoreMerchant.objects.count() == 0

    json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
    json_return_value["merchantId"] = "1234"
    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            merchant_create_url,
            json=json_return_value,
        )

        assert_update_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 2

    assert WebStoreMerchant.objects.count() == 2


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_can_patch_organization_with_more_than_one_web_store_merchant(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    merchant_data = default_web_store_merchants_data[0].copy()
    merchant_data2 = {
        "active": True,
        "name": "Test Merchant 2",
        "street_address": "Street Address 2",
        "zipcode": "12345",
        "city": "Test City",
        "email": "test2@test.dev",
        "phone_number": "+3580000001",
        "terms_of_service_url": "https://test2.dev/terms_of_service/",
        "business_id": "1234567-9",
        "paytrail_merchant_id": "12345678",
    }
    payload = {
        "web_store_merchants": [merchant_data, merchant_data2],
    }

    assert WebStoreMerchant.objects.count() == 0

    json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
    json_return_value["merchantId"] = "1234"
    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            merchant_create_url,
            json=json_return_value,
        )

        assert_patch_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 2

    assert WebStoreMerchant.objects.count() == 2


@pytest.mark.django_db
def test_create_organization_with_web_store_merchant_api_field_exception(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": default_web_store_merchants_data,
    }

    assert Organization.objects.count() == 1
    assert WebStoreMerchant.objects.count() == 0

    json_return_value = {
        "errors": [{"code": "test", "message": "Merchant already exists."}]
    }
    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            merchant_create_url,
            status_code=status.HTTP_400_BAD_REQUEST,
            json=json_return_value,
        )

        response = create_organization(api_client, payload)

        assert req_mock.call_count == 1

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data[0] == (
        f"Talpa web store API error (status_code: {status.HTTP_400_BAD_REQUEST}): "
        f"{json_return_value['errors']}"
    )

    assert Organization.objects.count() == 1
    assert WebStoreMerchant.objects.count() == 0


@pytest.mark.django_db
def test_create_organization_with_web_store_merchant_api_unknown_exception(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": default_web_store_merchants_data,
    }

    assert Organization.objects.count() == 1
    assert WebStoreMerchant.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            merchant_create_url, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

        response = create_organization(api_client, payload)

        assert req_mock.call_count == 1

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data[0] == (
        f"Unknown Talpa web store API error (status_code: {status.HTTP_500_INTERNAL_SERVER_ERROR})"
    )

    assert Organization.objects.count() == 1
    assert WebStoreMerchant.objects.count() == 0


@pytest.mark.django_db
def test_update_organization_with_web_store_merchant_api_field_exception(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": default_web_store_merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 0

    json_return_value = {
        "errors": [{"code": "test", "message": "Merchant already exists."}]
    }
    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            merchant_create_url,
            status_code=status.HTTP_400_BAD_REQUEST,
            json=json_return_value,
        )

        response = update_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 1

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data[0] == (
        f"Talpa web store API error (status_code: {status.HTTP_400_BAD_REQUEST}): "
        f"{json_return_value['errors']}"
    )

    assert WebStoreMerchant.objects.count() == 0


@pytest.mark.django_db
def test_update_organization_with_web_store_merchant_api_unknown_exception(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": default_web_store_merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            merchant_create_url, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

        response = update_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 1

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data[0] == (
        f"Unknown Talpa web store API error (status_code: {status.HTTP_500_INTERNAL_SERVER_ERROR})"
    )

    assert WebStoreMerchant.objects.count() == 0


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_do_not_update_web_store_merchant_in_talpa_if_data_is_unchanged(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    if user_role == "financial_admin":
        user.admin_organizations.add(organization)

    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=organization)

    origin_id = "test_organization2"

    web_store_merchants_data = [
        {
            "id": merchant.pk,
            **{
                field: getattr(merchant, field)
                for field in WebStoreMerchant._TALPA_SYNCED_FIELDS
            },
        }
    ]
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": web_store_merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 1

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/update/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}",
        )

        assert_update_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 0

    assert WebStoreMerchant.objects.count() == 1

    merchant.refresh_from_db()
    for field, value in web_store_merchants_data[0].items():
        assert getattr(merchant, field) == value


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.parametrize(
    "merchant_attr", [field for field in WebStoreMerchant._TALPA_SYNCED_FIELDS]
)
@pytest.mark.django_db
def test_do_not_patch_web_store_merchant_in_talpa_if_data_is_unchanged(
    data_source, organization, api_client, user_role, merchant_attr
):
    user = create_user_by_role(user_role, organization)
    if user_role == "financial_admin":
        user.admin_organizations.add(organization)

    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=organization)

    web_store_merchants_data = [
        {"id": merchant.pk, merchant_attr: getattr(merchant, merchant_attr)}
    ]
    payload = {
        "web_store_merchants": web_store_merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 1

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{django_settings.WEB_STORE_API_BASE_URL}merchant/update/merchant/"
            f"{django_settings.WEB_STORE_API_NAMESPACE}/{merchant.merchant_id}",
            json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
        )

        assert_patch_organization(api_client, organization.id, payload)

        assert req_mock.call_count == 0

    assert WebStoreMerchant.objects.count() == 1

    merchant.refresh_from_db()
    assert (
        getattr(merchant, merchant_attr) == web_store_merchants_data[0][merchant_attr]
    )


@pytest.mark.django_db
def test_superuser_can_create_organization_with_web_store_account(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_accounts": default_web_store_accounts_data,
    }

    assert WebStoreAccount.objects.count() == 0

    response = assert_create_organization(api_client, payload)
    assert len(response.data["web_store_accounts"]) == 1

    assert WebStoreAccount.objects.count() == 1
    assert (
        WebStoreAccount.objects.filter(
            organization_id=response.data["id"],
            created_by=user,
            last_modified_by=user,
            created_time__isnull=False,
            last_modified_time__isnull=False,
            **payload["web_store_accounts"][0],
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_superuser_can_update_organization_with_web_store_account(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_accounts": default_web_store_accounts_data,
    }

    assert WebStoreAccount.objects.count() == 0

    response = assert_update_organization(api_client, organization.id, payload)
    assert len(response.data["web_store_accounts"]) == 1

    assert WebStoreAccount.objects.count() == 1
    assert (
        WebStoreAccount.objects.filter(
            organization_id=response.data["id"],
            created_by=user,
            last_modified_by=user,
            created_time__isnull=False,
            last_modified_time__isnull=False,
            **payload["web_store_accounts"][0],
        ).count()
        == 1
    )


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_superuser_and_financial_admin_can_patch_organization_with_web_store_account(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    payload = {
        "web_store_accounts": default_web_store_accounts_data,
    }

    assert WebStoreAccount.objects.count() == 0

    response = assert_patch_organization(api_client, organization.id, payload)
    assert len(response.data["web_store_accounts"]) == 1

    assert WebStoreAccount.objects.count() == 1
    assert (
        WebStoreAccount.objects.filter(
            organization_id=response.data["id"],
            created_by=user,
            last_modified_by=user,
            created_time__isnull=False,
            last_modified_time__isnull=False,
            **payload["web_store_accounts"][0],
        ).count()
        == 1
    )


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_superuser_and_financial_can_patch_organizations_web_store_accounts(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    account = WebStoreAccountFactory(organization=organization)
    account2 = WebStoreAccountFactory(organization=organization)

    accounts_data = default_web_store_accounts_data[0].copy()
    accounts_data["id"] = account.pk

    accounts_data2 = default_web_store_accounts_data[0].copy()
    accounts_data2["id"] = account2.pk
    accounts_data2["name"] = "Test account 2"

    payload = {
        "web_store_accounts": [accounts_data, accounts_data2],
    }

    assert WebStoreAccount.objects.count() == 2
    assert (
        WebStoreAccount.objects.filter(
            organization_id=organization.id, **payload["web_store_accounts"][0]
        ).count()
        == 0
    )
    assert (
        WebStoreAccount.objects.filter(
            organization_id=organization.id, **payload["web_store_accounts"][1]
        ).count()
        == 0
    )

    assert account.last_modified_by is None
    last_modified_time = account.last_modified_time

    assert account2.last_modified_by is None
    last_modified_time2 = account2.last_modified_time

    response = assert_patch_organization(api_client, organization.id, payload)
    assert len(response.data["web_store_accounts"]) == 2

    assert WebStoreAccount.objects.count() == 2
    assert (
        WebStoreAccount.objects.filter(
            organization_id=organization.id, **payload["web_store_accounts"][0]
        ).count()
        == 1
    )
    assert (
        WebStoreAccount.objects.filter(
            organization_id=organization.id, **payload["web_store_accounts"][1]
        ).count()
        == 1
    )

    account.refresh_from_db()
    assert account.last_modified_by == user
    assert account.last_modified_time > last_modified_time

    account2.refresh_from_db()
    assert account2.last_modified_by == user
    assert account2.last_modified_time > last_modified_time2


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_superuser_and_financial_can_make_web_store_account_inactive(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    account = WebStoreAccountFactory(organization=organization)

    payload = {
        "web_store_accounts": [
            {
                "id": account.pk,
                "active": False,
            }
        ],
    }

    assert WebStoreAccount.objects.count() == 1
    assert account.active is True
    assert account.last_modified_by is None
    last_modified_time = account.last_modified_time

    response = assert_patch_organization(api_client, organization.id, payload)
    assert len(response.data["web_store_accounts"]) == 1

    account.refresh_from_db()
    assert WebStoreAccount.objects.count() == 1
    assert account.active is False
    assert account.last_modified_by == user
    assert account.last_modified_time > last_modified_time


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "registration_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_create_an_organization_with_a_web_store_account(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_accounts": default_web_store_accounts_data,
    }

    assert WebStoreAccount.objects.count() == 0

    response = create_organization(api_client, payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_accounts") is None

    assert WebStoreAccount.objects.count() == 0


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "registration_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_update_an_organization_with_a_web_store_account(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_accounts": default_web_store_accounts_data,
    }

    assert WebStoreAccount.objects.count() == 0

    response = update_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_accounts") is None

    assert WebStoreAccount.objects.count() == 0


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "registration_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_update_an_organizations_web_store_account(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    account = WebStoreAccountFactory(organization=organization)

    origin_id = "test_organization2"

    accounts_data = default_web_store_accounts_data[0].copy()
    accounts_data["id"] = account.pk

    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_accounts": [accounts_data],
    }

    assert WebStoreAccount.objects.count() == 1

    response = update_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_accounts") is None

    assert WebStoreAccount.objects.count() == 1


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "registration_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_patch_an_organizations_web_store_account(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    account = WebStoreAccountFactory(organization=organization)

    accounts_data = default_web_store_accounts_data[0].copy()
    accounts_data["id"] = account.pk
    payload = {
        "web_store_accounts": [accounts_data],
    }

    assert WebStoreAccount.objects.count() == 1

    response = patch_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_accounts") is None

    assert WebStoreAccount.objects.count() == 1


@pytest.mark.parametrize(
    "user_role",
    [
        "superuser",
        "financial_admin",
        "admin",
        "registration_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_users_can_get_organization_with_all_web_store_account_fields(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    WebStoreAccountFactory(organization=organization)

    response = get_organization(api_client, organization.id)
    assert response.status_code == status.HTTP_200_OK
    assert_account_fields_exist(response.data["web_store_accounts"][0])


@pytest.mark.django_db
def test_can_create_organization_with_more_than_one_web_store_account(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"

    account_data = default_web_store_accounts_data[0].copy()
    account_data2 = {
        "active": True,
        "name": "Test Account 2",
        "company_code": "2234",
        "main_ledger_account": "223456",
        "balance_profit_center": "2234567890",
    }

    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_accounts": [account_data, account_data2],
    }

    assert WebStoreAccount.objects.count() == 0

    assert_create_organization(api_client, payload)

    assert WebStoreAccount.objects.count() == 2


@pytest.mark.django_db
def test_can_update_organization_with_more_than_one_web_store_account(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"

    account_data = default_web_store_accounts_data[0].copy()
    account_data2 = {
        "active": True,
        "name": "Test Account 2",
        "company_code": "2234",
        "main_ledger_account": "223456",
        "balance_profit_center": "2234567890",
    }

    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_accounts": [account_data, account_data2],
    }

    assert WebStoreAccount.objects.count() == 0

    assert_update_organization(api_client, organization.id, payload)

    assert WebStoreAccount.objects.count() == 2


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_can_patch_organization_with_more_than_one_web_store_account(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    account_data = default_web_store_accounts_data[0].copy()
    account_data2 = {
        "active": True,
        "name": "Test Account 2",
        "company_code": "2234",
        "main_ledger_account": "223456",
        "balance_profit_center": "2234567890",
    }
    payload = {
        "web_store_accounts": [account_data, account_data2],
    }

    assert WebStoreAccount.objects.count() == 0

    assert_patch_organization(api_client, organization.id, payload)

    assert WebStoreAccount.objects.count() == 2


@pytest.mark.parametrize(
    "user2_with_user_type, expected_status",
    [
        ("superuser", status.HTTP_200_OK),
        ("org_admin", status.HTTP_200_OK),
        ("org_registration_admin", status.HTTP_200_OK),
        ("org_financial_admin", status.HTTP_200_OK),
        ("org_regular", status.HTTP_403_FORBIDDEN),
        ("staff", status.HTTP_403_FORBIDDEN),
        ("admin", status.HTTP_403_FORBIDDEN),
        (None, status.HTTP_403_FORBIDDEN),
    ],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_get_organization_web_store_merchants(
    api_client, organization, user2_with_user_type, expected_status
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        WebStoreMerchantFactory(organization=organization)
        WebStoreMerchantFactory(organization=organization)

    api_client.force_authenticate(user2_with_user_type)

    response = get_organization_merchants(api_client, organization.id)
    assert response.status_code == expected_status

    if expected_status == status.HTTP_200_OK:
        assert len(response.data) == 2


@pytest.mark.parametrize(
    "user2_with_user_type, expected_status",
    [
        ("superuser", status.HTTP_200_OK),
        ("org_admin", status.HTTP_200_OK),
        ("org_registration_admin", status.HTTP_200_OK),
        ("org_financial_admin", status.HTTP_200_OK),
        ("org_regular", status.HTTP_403_FORBIDDEN),
        ("staff", status.HTTP_403_FORBIDDEN),
        ("admin", status.HTTP_403_FORBIDDEN),
        (None, status.HTTP_403_FORBIDDEN),
    ],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_get_organization_web_store_merchants_from_ancestor(
    api_client, organization, organization2, user2_with_user_type, expected_status
):
    organization2.admin_users.remove(user2_with_user_type)

    organization2.parent = organization
    organization2.save(update_fields=["parent"])

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        WebStoreMerchantFactory(organization=organization)
        WebStoreMerchantFactory(organization=organization)

    api_client.force_authenticate(user2_with_user_type)

    response = get_organization_merchants(api_client, organization2.id)
    assert response.status_code == expected_status

    if expected_status == status.HTTP_200_OK:
        assert len(response.data) == 2


@pytest.mark.parametrize(
    "user2_with_user_type, expected_status",
    [
        ("superuser", status.HTTP_200_OK),
        ("org_admin", status.HTTP_200_OK),
        ("org_registration_admin", status.HTTP_200_OK),
        ("org_financial_admin", status.HTTP_200_OK),
        ("org_regular", status.HTTP_403_FORBIDDEN),
        ("staff", status.HTTP_403_FORBIDDEN),
        ("admin", status.HTTP_403_FORBIDDEN),
        (None, status.HTTP_403_FORBIDDEN),
    ],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_get_organization_web_store_accounts(
    api_client, organization, user2_with_user_type, expected_status
):
    WebStoreAccountFactory(organization=organization)
    WebStoreAccountFactory(organization=organization)

    api_client.force_authenticate(user2_with_user_type)

    response = get_organization_accounts(api_client, organization.id)
    assert response.status_code == expected_status

    if expected_status == status.HTTP_200_OK:
        assert len(response.data) == 2


@pytest.mark.parametrize(
    "user2_with_user_type, expected_status",
    [
        ("superuser", status.HTTP_200_OK),
        ("org_admin", status.HTTP_200_OK),
        ("org_registration_admin", status.HTTP_200_OK),
        ("org_financial_admin", status.HTTP_200_OK),
        ("org_regular", status.HTTP_403_FORBIDDEN),
        ("staff", status.HTTP_403_FORBIDDEN),
        ("admin", status.HTTP_403_FORBIDDEN),
        (None, status.HTTP_403_FORBIDDEN),
    ],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_get_organization_web_store_accounts_from_ancestor(
    api_client, organization, organization2, user2_with_user_type, expected_status
):
    organization2.admin_users.remove(user2_with_user_type)

    organization2.parent = organization
    organization2.save(update_fields=["parent"])

    WebStoreAccountFactory(organization=organization)
    WebStoreAccountFactory(organization=organization)

    api_client.force_authenticate(user2_with_user_type)

    response = get_organization_accounts(api_client, organization2.id)
    assert response.status_code == expected_status

    if expected_status == status.HTTP_200_OK:
        assert len(response.data) == 2


@pytest.mark.django_db
def test_own_organization_api_key_can_get_organization_web_store_merchants(
    api_client, organization, data_source
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        WebStoreMerchantFactory(organization=organization)
        WebStoreMerchantFactory(organization=organization)

    data_source.user_editable_registrations = True
    data_source.owner = organization
    data_source.save(update_fields=["user_editable_registrations", "owner"])

    api_client.credentials(apikey=data_source.api_key)

    response = get_organization_merchants(api_client, organization.id)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2


@pytest.mark.django_db
def test_other_organization_api_key_cannot_get_organization_web_store_merchants(
    api_client, organization, organization2, data_source
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        WebStoreMerchantFactory(organization=organization)
        WebStoreMerchantFactory(organization=organization)

    data_source.user_editable_registrations = True
    data_source.owner = organization2
    data_source.save(update_fields=["user_editable_registrations", "owner"])

    api_client.credentials(apikey=data_source.api_key)

    response = get_organization_merchants(api_client, organization.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_invalid_api_key_cannot_get_organization_web_store_merchants(
    api_client, organization
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        WebStoreMerchantFactory(organization=organization)
        WebStoreMerchantFactory(organization=organization)

    api_client.credentials(apikey="wrong")

    response = get_organization_merchants(api_client, organization.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_own_organization_api_key_can_get_organization_web_store_accounts(
    api_client, organization, data_source
):
    WebStoreAccountFactory(organization=organization)
    WebStoreAccountFactory(organization=organization)

    data_source.user_editable_registrations = True
    data_source.owner = organization
    data_source.save(update_fields=["user_editable_registrations", "owner"])

    api_client.credentials(apikey=data_source.api_key)

    response = get_organization_accounts(api_client, organization.id)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2


@pytest.mark.django_db
def test_other_organization_api_key_cannot_get_organization_web_store_accounts(
    api_client, organization, organization2, data_source
):
    WebStoreAccountFactory(organization=organization)
    WebStoreAccountFactory(organization=organization)

    data_source.user_editable_registrations = True
    data_source.owner = organization2
    data_source.save(update_fields=["user_editable_registrations", "owner"])

    api_client.credentials(apikey=data_source.api_key)

    response = get_organization_accounts(api_client, organization.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_invalid_api_key_cannot_get_organization_web_store_accounts(
    api_client, organization
):
    WebStoreAccountFactory(organization=organization)
    WebStoreAccountFactory(organization=organization)

    api_client.credentials(apikey="wrong")

    response = get_organization_accounts(api_client, organization.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
@pytest.mark.django_db
def test_organization_web_store_merchants_disallowed_http_methods(
    user_api_client, organization, method
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        WebStoreMerchantFactory(organization=organization)
        WebStoreMerchantFactory(organization=organization)

    base_url = reverse(
        OrganizationDetailSerializer.view_name, kwargs={"pk": organization.pk}
    )
    url = f"{base_url}merchants/"

    response = getattr(user_api_client, method)(url, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
@pytest.mark.django_db
def test_organization_web_store_accounts_disallowed_http_methods(
    user_api_client, organization, method
):
    WebStoreAccountFactory(organization=organization)
    WebStoreAccountFactory(organization=organization)

    base_url = reverse(
        OrganizationDetailSerializer.view_name, kwargs={"pk": organization.pk}
    )
    url = f"{base_url}accounts/"

    response = getattr(user_api_client, method)(url, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    "request_function", [get_organization_merchants, get_organization_accounts]
)
@pytest.mark.parametrize(
    "user2_with_user_type",
    [
        "superuser",
        "org_admin",
        "org_registration_admin",
        "org_financial_admin",
    ],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_get_organization_web_store_merchants_and_accounts_empty_result(
    api_client, organization, request_function, user2_with_user_type
):
    api_client.force_authenticate(user2_with_user_type)

    response = request_function(api_client, organization.id)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 0


@pytest.mark.parametrize(
    "user2_with_user_type",
    [
        "superuser",
        "org_admin",
        "org_registration_admin",
        "org_financial_admin",
    ],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_get_organization_web_store_merchants_integration_disabled_404(
    api_client, organization, settings, user2_with_user_type
):
    settings.WEB_STORE_INTEGRATION_ENABLED = False

    WebStoreMerchantFactory(organization=organization)
    WebStoreMerchantFactory(organization=organization)

    api_client.force_authenticate(user2_with_user_type)

    response = get_organization_merchants(api_client, organization.id)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    "user2_with_user_type",
    [
        "superuser",
        "org_admin",
        "org_registration_admin",
        "org_financial_admin",
    ],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_get_organization_web_store_accounts_integration_disabled_404(
    api_client, organization, settings, user2_with_user_type
):
    settings.WEB_STORE_INTEGRATION_ENABLED = False

    WebStoreAccountFactory(organization=organization)
    WebStoreAccountFactory(organization=organization)

    api_client.force_authenticate(user2_with_user_type)

    response = get_organization_accounts(api_client, organization.id)
    assert response.status_code == status.HTTP_404_NOT_FOUND
