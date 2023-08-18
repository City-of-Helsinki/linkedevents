import pytest
from django_orghierarchy.models import Organization
from rest_framework import status

from events.api import OrganizationDetailSerializer
from events.tests.factories import OrganizationFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory

organization_name = "test org"
edited_organization_name = "new name"


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


def assert_update_organization(api_client, pk, organization_data):
    response = update_organization(api_client, pk, organization_data)
    assert response.status_code == status.HTTP_200_OK
    return response


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
    assert response.data.get("admin_users") == None
    assert response.data.get("regular_users") == None


@pytest.mark.django_db
def test_regular_user_cannot_see_organization_users(
    organization, user, user_api_client
):
    organization.regular_users.add(user)
    organization.admin_users.remove(user)

    response = get_organization(user_api_client, organization.id)
    assert response.data.get("admin_users") == None
    assert response.data.get("regular_users") == None


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
    data_source, user, user_api_client
):
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
    data_source, user, user2, user_api_client
):
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
def test_admin_user_can_update_organization(organization, user_api_client):
    payload = {
        "id": organization.id,
        "name": edited_organization_name,
    }

    response = assert_update_organization(user_api_client, organization.id, payload)
    assert response.data["name"] == payload["name"]


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
