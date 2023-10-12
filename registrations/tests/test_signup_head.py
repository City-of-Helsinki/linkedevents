from typing import Union

import pytest
from rest_framework import status

from events.tests.conftest import APIClient
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.tests.factories import SignUpFactory

# === util methods ===


def head_list(api_client: APIClient):
    url = reverse("signup-list")

    return api_client.head(url)


def head_detail(api_client: APIClient, pk: Union[str, int]):
    url = reverse("signup-detail", kwargs={"pk": pk})

    return api_client.head(url)


# === tests ===


@pytest.mark.parametrize("url_type", ["list", "detail"])
@pytest.mark.django_db
def test_head_method_not_allowed_for_signup(api_client, registration, url_type):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    if url_type == "list":
        response = head_list(api_client)
    else:
        signup = SignUpFactory(registration=registration)
        response = head_detail(api_client, pk=signup.pk)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
