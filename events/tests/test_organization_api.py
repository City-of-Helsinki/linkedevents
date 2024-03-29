from unittest.mock import patch

import pytest
from django.utils import translation
from django_orghierarchy.models import Organization
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.api import OrganizationDetailSerializer
from events.tests.utils import assert_fields_exist
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import WebStoreMerchant
from registrations.tests.factories import WebStoreMerchantFactory
from registrations.tests.utils import create_user_by_role
from web_store.tests.merchant.test_web_store_merchant_api_client import (
    DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
)
from web_store.tests.utils import get_mock_response

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
        "url": "https://test.dev/homepage/",
        "terms_of_service_url": "https://test.dev/terms_of_service/",
        "business_id": "1234567-8",
        "paytrail_merchant_id": "1234567",
    }
]


def organization_id(pk):
    obj_id = reverse(OrganizationDetailSerializer.view_name, kwargs={"pk": pk})
    return obj_id


def get_organization(api_client, pk):
    url = reverse(OrganizationDetailSerializer.view_name, kwargs={"pk": pk})

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


def patch_organization(api_client, pk, organization_data):
    url = reverse(OrganizationDetailSerializer.view_name, kwargs={"pk": pk})

    response = api_client.patch(url, organization_data, format="json")
    return response


def assert_update_organization(api_client, pk, organization_data):
    response = update_organization(api_client, pk, organization_data)
    assert response.status_code == status.HTTP_200_OK
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


@pytest.fixture
def user2_with_user_type(organization, user2, request):
    user_type = request.param
    if user_type == "org_regular":
        organization.regular_users.add(user2)

    elif user_type == "org_admin":
        organization.admin_users.add(user2)

    elif user_type == "staff":
        user2.is_staff = True
        user2.save()

    elif user_type == "admin":
        user2.is_staff = True
        user2.is_admin = True
        user2.save()

    elif user_type == "superuser":
        user2.is_staff = True
        user2.is_admin = True
        user2.is_superuser = True
        user2.save()

    elif user_type is None:
        pass

    else:
        raise ValueError("user_type was not handled in test")

    return user2


@pytest.mark.parametrize(
    "user2_with_user_type, expected_status",
    [
        (None, status.HTTP_403_FORBIDDEN),
        ("org_regular", status.HTTP_403_FORBIDDEN),
        ("org_admin", status.HTTP_201_CREATED),
        ("staff", status.HTTP_403_FORBIDDEN),
        ("admin", status.HTTP_403_FORBIDDEN),
        ("superuser", status.HTTP_403_FORBIDDEN),
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
        ("superuser", status.HTTP_403_FORBIDDEN),
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
        ("superuser", status.HTTP_403_FORBIDDEN),
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


@pytest.mark.django_db
def test_superuser_can_create_organization_with_web_store_merchant(
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

    json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
    json_return_value["merchantId"] = "1234"
    mocked_web_store_api_response = get_mock_response(
        json_return_value=json_return_value,
    )
    with patch("requests.post") as mocked_web_store_api_request:
        mocked_web_store_api_request.return_value = mocked_web_store_api_response

        response = assert_create_organization(api_client, payload)
    assert mocked_web_store_api_request.called is True
    assert len(response.data["web_store_merchants"]) == 1

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=response.data["id"],
            merchant_id=response.data["web_store_merchants"][0]["merchant_id"],
            created_by=user,
            last_modified_by=user,
            created_time__isnull=False,
            last_modified_time__isnull=False,
            **payload["web_store_merchants"][0],
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_superuser_can_update_organization_with_web_store_merchant(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser")
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

    json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
    json_return_value["merchantId"] = "1234"
    mocked_web_store_api_response = get_mock_response(
        json_return_value=json_return_value,
    )
    with patch("requests.post") as mocked_web_store_api_request:
        mocked_web_store_api_request.return_value = mocked_web_store_api_response

        response = assert_update_organization(api_client, organization.id, payload)
    assert mocked_web_store_api_request.called is True
    assert len(response.data["web_store_merchants"]) == 1

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=response.data["id"],
            merchant_id=response.data["web_store_merchants"][0]["merchant_id"],
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

    json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
    json_return_value["merchantId"] = "1234"
    mocked_web_store_api_response = get_mock_response(
        json_return_value=json_return_value,
    )
    with patch("requests.post") as mocked_web_store_api_request:
        mocked_web_store_api_request.return_value = mocked_web_store_api_response

        response = assert_patch_organization(api_client, organization.id, payload)
    assert mocked_web_store_api_request.called is True
    assert len(response.data["web_store_merchants"]) == 1

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=response.data["id"],
            merchant_id=response.data["web_store_merchants"][0]["merchant_id"],
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
    data_source, organization, api_client, settings, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    settings.WEB_STORE_INTEGRATION_ENABLED = False
    merchant = WebStoreMerchantFactory(organization=organization, merchant_id="1234")
    settings.WEB_STORE_INTEGRATION_ENABLED = True

    merchants_data = default_web_store_merchants_data[0].copy()
    merchants_data["id"] = merchant.pk
    payload = {
        "web_store_merchants": [merchants_data],
    }

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=organization.id, **payload["web_store_merchants"][0]
        ).count()
        == 0
    )
    assert merchant.last_modified_by is None
    last_modified_time = merchant.last_modified_time

    json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
    mocked_web_store_api_response = get_mock_response(
        status_code=status.HTTP_200_OK,
        json_return_value=json_return_value,
    )
    with patch("requests.post") as mocked_web_store_api_request:
        mocked_web_store_api_request.return_value = mocked_web_store_api_response

        response = assert_patch_organization(api_client, organization.id, payload)
    assert mocked_web_store_api_request.called is True
    assert len(response.data["web_store_merchants"]) == 1

    assert WebStoreMerchant.objects.count() == 1
    assert (
        WebStoreMerchant.objects.filter(
            organization_id=organization.id, **payload["web_store_merchants"][0]
        ).count()
        == 1
    )
    merchant.refresh_from_db()
    assert merchant.last_modified_by == user
    assert merchant.last_modified_time > last_modified_time


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_superuser_and_financial_can_make_web_store_merchant_inactive(
    data_source, organization, api_client, settings, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    settings.WEB_STORE_INTEGRATION_ENABLED = False
    merchant = WebStoreMerchantFactory(organization=organization, merchant_id="1234")
    settings.WEB_STORE_INTEGRATION_ENABLED = True

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

    with patch("requests.post") as mocked_web_store_api_request:
        response = assert_patch_organization(api_client, organization.id, payload)
    assert mocked_web_store_api_request.called is False
    assert len(response.data["web_store_merchants"]) == 1

    merchant.refresh_from_db()
    assert WebStoreMerchant.objects.count() == 1
    assert merchant.active is False
    assert merchant.last_modified_by == user
    assert merchant.last_modified_time > last_modified_time


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

    with patch("requests.post") as mocked_web_store_api_request:
        response = create_organization(api_client, payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_merchants") is None
    assert mocked_web_store_api_request.called is False

    assert WebStoreMerchant.objects.count() == 0


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

    with patch("requests.post") as mocked_web_store_api_request:
        response = update_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_merchants") is None
    assert mocked_web_store_api_request.called is False

    assert WebStoreMerchant.objects.count() == 0


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
def test_not_allowed_user_roles_cannot_update_an_organizations_web_store_merchant(
    data_source, organization, api_client, settings, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    settings.WEB_STORE_INTEGRATION_ENABLED = False
    merchant = WebStoreMerchantFactory(organization=organization, merchant_id="1234")
    settings.WEB_STORE_INTEGRATION_ENABLED = True

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

    with patch("requests.post") as mocked_web_store_api_request:
        response = update_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_merchants") is None
    assert mocked_web_store_api_request.called is False

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
    data_source, organization, api_client, settings, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    settings.WEB_STORE_INTEGRATION_ENABLED = False
    merchant = WebStoreMerchantFactory(organization=organization, merchant_id="1234")
    settings.WEB_STORE_INTEGRATION_ENABLED = True

    merchants_data = default_web_store_merchants_data[0].copy()
    merchants_data["id"] = merchant.pk
    payload = {
        "web_store_merchants": [merchants_data],
    }

    assert WebStoreMerchant.objects.count() == 1

    with patch("requests.post") as mocked_web_store_api_request:
        response = patch_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data.get("web_store_merchants") is None
    assert mocked_web_store_api_request.called is False

    assert WebStoreMerchant.objects.count() == 1


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_superuser_and_financial_admin_can_get_organization_with_all_web_store_merchant_fields(
    data_source, organization, api_client, settings, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    settings.WEB_STORE_INTEGRATION_ENABLED = False
    WebStoreMerchantFactory(organization=organization, merchant_id="1234")
    settings.WEB_STORE_INTEGRATION_ENABLED = True

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
    data_source, organization, api_client, settings, user_role
):
    user = create_user_by_role(
        user_role,
        organization if user_role != "regular_user_without_organization" else None,
        additional_roles={"regular_user_without_organization": lambda usr: None},
    )
    api_client.force_authenticate(user)

    settings.WEB_STORE_INTEGRATION_ENABLED = False
    WebStoreMerchantFactory(organization=organization, merchant_id="1234")
    settings.WEB_STORE_INTEGRATION_ENABLED = True

    response = get_organization(api_client, organization.id)
    assert response.status_code == status.HTTP_200_OK
    assert_merchant_fields_exist(response.data["web_store_merchants"][0])


@pytest.mark.django_db
def test_cannot_create_organization_with_more_than_one_web_store_merchant(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"

    merchants_data = default_web_store_merchants_data.copy()
    merchants_data.append(
        {
            "active": True,
            "name": "Test Merchant 2",
            "street_address": "Street Address 2",
            "zipcode": "12345",
            "city": "Test City",
            "email": "test2@test.dev",
            "phone_number": "+3580000001",
            "url": "https://test2.dev/homepage/",
            "terms_of_service_url": "https://test2.dev/terms_of_service/",
            "business_id": "1234567-9",
            "paytrail_merchant_id": "12345678",
        }
    )

    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 0

    with patch("requests.post") as mocked_web_store_api_request:
        response = create_organization(api_client, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["web_store_merchants"]["non_field_errors"][0] == (
        "Ensure this field has no more than 1 elements."
    )
    assert mocked_web_store_api_request.called is False

    assert WebStoreMerchant.objects.count() == 0


@pytest.mark.django_db
def test_cannot_update_organization_with_more_than_one_web_store_merchant(
    data_source, organization, api_client
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    origin_id = "test_organization2"

    merchants_data = default_web_store_merchants_data.copy()
    merchants_data.append(
        {
            "active": True,
            "name": "Test Merchant 2",
            "street_address": "Street Address 2",
            "zipcode": "12345",
            "city": "Test City",
            "email": "test2@test.dev",
            "phone_number": "+3580000001",
            "url": "https://test2.dev/homepage/",
            "terms_of_service_url": "https://test2.dev/terms_of_service/",
            "business_id": "1234567-9",
            "paytrail_merchant_id": "12345678",
        }
    )

    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 0

    with patch("requests.post") as mocked_web_store_api_request:
        response = update_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["web_store_merchants"]["non_field_errors"][0] == (
        "Ensure this field has no more than 1 elements."
    )
    assert mocked_web_store_api_request.called is False

    assert WebStoreMerchant.objects.count() == 0


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_cannot_patch_organization_with_more_than_one_web_store_merchant(
    data_source, organization, api_client, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    merchants_data = default_web_store_merchants_data.copy()
    merchants_data.append(
        {
            "active": True,
            "name": "Test Merchant 2",
            "street_address": "Street Address 2",
            "zipcode": "12345",
            "city": "Test City",
            "email": "test2@test.dev",
            "phone_number": "+3580000001",
            "url": "https://test2.dev/homepage/",
            "terms_of_service_url": "https://test2.dev/terms_of_service/",
            "business_id": "1234567-9",
            "paytrail_merchant_id": "12345678",
        }
    )
    payload = {
        "web_store_merchants": merchants_data,
    }

    assert WebStoreMerchant.objects.count() == 0

    with patch("requests.post") as mocked_web_store_api_request:
        response = patch_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["web_store_merchants"]["non_field_errors"][0] == (
        "Ensure this field has no more than 1 elements."
    )
    assert mocked_web_store_api_request.called is False

    assert WebStoreMerchant.objects.count() == 0


@pytest.mark.django_db
def test_always_update_existing_web_store_merchant(
    data_source, organization, api_client, settings
):
    user = create_user_by_role("superuser", None)

    api_client.force_authenticate(user)

    settings.WEB_STORE_INTEGRATION_ENABLED = False
    merchant = WebStoreMerchantFactory(organization=organization, merchant_id="1234")
    settings.WEB_STORE_INTEGRATION_ENABLED = True

    origin_id = "test_organization2"
    payload = {
        "data_source": data_source.id,
        "origin_id": origin_id,
        "id": f"{data_source.id}:{origin_id}",
        "name": organization_name,
        "web_store_merchants": [
            {
                "active": True,
                "name": "Test Merchant 2",
                "street_address": "Street Address 2",
                "zipcode": "12345",
                "city": "Test City",
                "email": "test2@test.dev",
                "phone_number": "+3580000001",
                "url": "https://test2.dev/homepage/",
                "terms_of_service_url": "https://test2.dev/terms_of_service/",
                "business_id": "1234567-9",
                "paytrail_merchant_id": "12345678",
            },
        ],
    }

    assert WebStoreMerchant.objects.count() == 1
    for field, value in payload["web_store_merchants"][0].items():
        if field == "active":
            assert getattr(merchant, field) is value
        else:
            assert getattr(merchant, field) != value

    json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
    mocked_web_store_api_response = get_mock_response(
        status_code=status.HTTP_200_OK,
        json_return_value=json_return_value,
    )
    with patch("requests.post") as mocked_web_store_api_request:
        mocked_web_store_api_request.return_value = mocked_web_store_api_response

        assert_update_organization(api_client, organization.id, payload)
    assert mocked_web_store_api_request.called is True

    merchant.refresh_from_db()
    assert WebStoreMerchant.objects.count() == 1
    for field, value in payload["web_store_merchants"][0].items():
        if field == "active":
            assert getattr(merchant, field) is value
        else:
            assert getattr(merchant, field) == value


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_always_patch_existing_web_store_merchant(
    data_source, organization, api_client, settings, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    settings.WEB_STORE_INTEGRATION_ENABLED = False
    merchant = WebStoreMerchantFactory(organization=organization, merchant_id="1234")
    settings.WEB_STORE_INTEGRATION_ENABLED = True

    payload = {
        "web_store_merchants": [
            {
                "active": True,
                "name": "Test Merchant 2",
                "street_address": "Street Address 2",
                "zipcode": "12345",
                "city": "Test City",
                "email": "test2@test.dev",
                "phone_number": "+3580000001",
                "url": "https://test2.dev/homepage/",
                "terms_of_service_url": "https://test2.dev/terms_of_service/",
                "business_id": "1234567-9",
                "paytrail_merchant_id": "12345678",
            },
        ],
    }

    assert WebStoreMerchant.objects.count() == 1
    for field, value in payload["web_store_merchants"][0].items():
        if field == "active":
            assert getattr(merchant, field) is value
        else:
            assert getattr(merchant, field) != value

    json_return_value = DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA.copy()
    mocked_web_store_api_response = get_mock_response(
        status_code=status.HTTP_200_OK,
        json_return_value=json_return_value,
    )
    with patch("requests.post") as mocked_web_store_api_request:
        mocked_web_store_api_request.return_value = mocked_web_store_api_response

        assert_patch_organization(api_client, organization.id, payload)
    assert mocked_web_store_api_request.called is True

    merchant.refresh_from_db()
    assert WebStoreMerchant.objects.count() == 1
    for field, value in payload["web_store_merchants"][0].items():
        if field == "active":
            assert getattr(merchant, field) is value
        else:
            assert getattr(merchant, field) == value


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
    mocked_web_store_api_response = get_mock_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        exception_json_return_value=json_return_value,
    )
    with patch("requests.post") as mocked_web_store_api_request:
        mocked_web_store_api_request.return_value = mocked_web_store_api_response

        response = create_organization(api_client, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert mocked_web_store_api_request.called is True
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

    mocked_web_store_api_response = get_mock_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    with patch("requests.post") as mocked_web_store_api_request:
        mocked_web_store_api_request.return_value = mocked_web_store_api_response

        response = create_organization(api_client, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert mocked_web_store_api_request.called is True
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
    mocked_web_store_api_response = get_mock_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        exception_json_return_value=json_return_value,
    )
    with patch("requests.post") as mocked_web_store_api_request:
        mocked_web_store_api_request.return_value = mocked_web_store_api_response

        response = update_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data[0] == (
        f"Talpa web store API error (status_code: {status.HTTP_400_BAD_REQUEST}): "
        f"{json_return_value['errors']}"
    )
    assert mocked_web_store_api_request.called is True

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

    mocked_web_store_api_response = get_mock_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    with patch("requests.post") as mocked_web_store_api_request:
        mocked_web_store_api_request.return_value = mocked_web_store_api_response

        response = update_organization(api_client, organization.id, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data[0] == (
        f"Unknown Talpa web store API error (status_code: {status.HTTP_500_INTERNAL_SERVER_ERROR})"
    )
    assert mocked_web_store_api_request.called is True

    assert WebStoreMerchant.objects.count() == 0
