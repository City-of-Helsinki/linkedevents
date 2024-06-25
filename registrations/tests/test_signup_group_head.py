from typing import Union

import pytest
from rest_framework import status

from events.tests.conftest import APIClient
from events.tests.utils import versioned_reverse as reverse
from registrations.tests.factories import SignUpGroupFactory
from registrations.tests.utils import create_user_by_role

# === util methods ===


def head_list(api_client: APIClient):
    url = reverse("signupgroup-list")

    return api_client.head(url)


def head_detail(api_client: APIClient, pk: Union[str, int]):
    url = reverse("signupgroup-detail", kwargs={"pk": pk})

    return api_client.head(url)


# === tests ===


@pytest.mark.parametrize("url_type", ["list", "detail"])
@pytest.mark.django_db
def test_head_method_not_allowed_for_signup_group(api_client, registration, url_type):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    if url_type == "list":
        response = head_list(api_client)
    else:
        signup_group = SignUpGroupFactory(registration=registration)
        response = head_detail(api_client, pk=signup_group.pk)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
