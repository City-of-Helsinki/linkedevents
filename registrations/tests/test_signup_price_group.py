from typing import Union

import pytest
from rest_framework import status

from events.tests.conftest import APIClient
from events.tests.factories import ApiKeyUserFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUpPriceGroup
from registrations.tests.factories import (
    RegistrationUserAccessFactory,
    SignUpPriceGroupFactory,
)
from registrations.tests.test_registration_post import hel_email
from registrations.tests.utils import create_user_by_role

# === util methods ===


def delete_price_group(api_client: APIClient, signup_pk: Union[str, int]):
    url = reverse("signup-price-group", kwargs={"pk": signup_pk})

    return api_client.delete(url)


def assert_delete_price_group(
    api_client: APIClient, signup_pk: Union[str, int], price_groups_count=1
):
    assert SignUpPriceGroup.objects.count() == price_groups_count

    response = delete_price_group(api_client, signup_pk)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert SignUpPriceGroup.objects.count() == (price_groups_count - 1)


def assert_delete_price_group_failed(
    api_client: APIClient,
    signup_pk: Union[str, int],
    price_groups_count=1,
    status_code=status.HTTP_403_FORBIDDEN,
):
    assert SignUpPriceGroup.objects.count() == price_groups_count

    response = delete_price_group(api_client, signup_pk)
    assert response.status_code == status_code

    assert SignUpPriceGroup.objects.count() == price_groups_count


# === tests ===


@pytest.mark.parametrize("http_method", ["get", "post", "put", "patch", "head"])
@pytest.mark.django_db
def test_wrong_http_method_not_allowed(api_client, signup, http_method):
    user = UserFactory(is_superuser=True)
    api_client.force_authenticate(user)

    url = reverse("signup-price-group", kwargs={"pk": signup.pk})
    response = getattr(api_client, http_method)(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.parametrize(
    "user_role",
    [
        "superuser",
        "admin",
        "registration_admin",
        "financial_admin",
        "regular_user",
        "regular_user_without_organization",
        "registration_user_access",
        "registration_substitute_user",
    ],
)
@pytest.mark.django_db
def test_delete_signup_price_group_allowed(api_client, signup, user_role):
    SignUpPriceGroupFactory(signup=signup)

    user = create_user_by_role(
        user_role,
        signup.publisher,
        additional_roles={
            "regular_user_without_organization": lambda usr: None,
            "registration_user_access": lambda usr: RegistrationUserAccessFactory(
                registration=signup.registration, email=usr.email
            ),
            "registration_substitute_user": lambda usr: RegistrationUserAccessFactory(
                registration=signup.registration,
                email=hel_email,
                is_substitute_user=True,
            ),
        },
    )

    if user_role == "registration_substitute_user":
        user.email = hel_email
        user.save(update_fields=["email"])

    api_client.force_authenticate(user)

    if user_role not in (
        "superuser",
        "registration_admin",
        "registration_substitute_user",
    ):
        signup.created_by = user
        signup.save(update_fields=["created_by"])

    assert_delete_price_group(api_client, signup.pk)


@pytest.mark.django_db
def test_apikey_delete_signup_price_group_allowed(api_client, signup):
    SignUpPriceGroupFactory(signup=signup)

    data_source = signup.data_source
    data_source.owner = signup.publisher
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])

    ApiKeyUserFactory(data_source=data_source)
    api_client.credentials(apikey=data_source.api_key)

    assert_delete_price_group(api_client, signup.pk)


@pytest.mark.parametrize(
    "user_role",
    [
        "admin",
        "financial_admin",
        "regular_user",
        "regular_user_without_organization",
    ],
)
@pytest.mark.django_db
def test_delete_signup_price_group_forbidden(api_client, signup, user_role):
    SignUpPriceGroupFactory(signup=signup)

    user = create_user_by_role(
        user_role,
        signup.publisher,
        additional_roles={
            "regular_user_without_organization": lambda usr: None,
        },
    )
    api_client.force_authenticate(user)

    assert_delete_price_group_failed(api_client, signup.pk)


@pytest.mark.parametrize(
    "owner,user_editable_registrations",
    [
        ("organization", False),
        ("organization2", True),
        (None, False),
        (None, True),
    ],
)
@pytest.mark.django_db
def test_apikey_delete_signup_price_group_forbidden(
    api_client, signup, organization2, owner, user_editable_registrations
):
    SignUpPriceGroupFactory(signup=signup)

    data_source = signup.data_source

    data_source_mapping = {
        "organization": lambda ds: setattr(ds, "owner", signup.publisher),
        "organization2": lambda ds: setattr(ds, "owner", organization2),
        None: lambda ds: setattr(ds, "owner", None),
    }
    data_source_mapping[owner](data_source)

    data_source.user_editable_registrations = user_editable_registrations
    data_source.save(update_fields=["owner", "user_editable_registrations"])

    ApiKeyUserFactory(data_source=data_source)
    api_client.credentials(apikey=data_source.api_key)

    assert_delete_price_group_failed(api_client, signup.pk)


@pytest.mark.django_db
def test_unknown_apikey_delete_signup_price_group_not_authorized(api_client, signup):
    SignUpPriceGroupFactory(signup=signup)

    api_client.credentials(apikey="unkown")

    assert_delete_price_group_failed(
        api_client, signup.pk, status_code=status.HTTP_401_UNAUTHORIZED
    )


@pytest.mark.django_db
def test_delete_signup_price_group_not_found(api_client, signup):
    user = UserFactory(is_superuser=True)
    api_client.force_authenticate(user)

    response = delete_price_group(api_client, signup.pk)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_cannot_delete_soft_deleted_signup_price_group(api_client, signup):
    price_group = SignUpPriceGroupFactory(signup=signup)
    price_group.soft_delete()

    user = create_user_by_role(
        "registration_admin",
        signup.publisher,
    )
    api_client.force_authenticate(user)

    assert SignUpPriceGroup.all_objects.count() == 1

    assert_delete_price_group_failed(
        api_client,
        signup.pk,
        status_code=status.HTTP_404_NOT_FOUND,
        price_groups_count=0,
    )

    assert SignUpPriceGroup.all_objects.count() == 1
