from typing import Union

import pytest
from rest_framework import status

from events.tests.conftest import APIClient
from events.tests.utils import versioned_reverse as reverse
from registrations.tests.factories import RegistrationFactory

# === util methods ===


def head_list(api_client: APIClient):
    url = reverse("registration-list")

    return api_client.head(url)


def head_detail(api_client: APIClient, pk: Union[str, int]):
    url = reverse("registration-detail", kwargs={"pk": pk})

    return api_client.head(url)


# === tests ===


@pytest.mark.parametrize("url_type", ["list", "detail"])
@pytest.mark.django_db
def test_head_method_not_allowed_for_registration(user_api_client, url_type):
    if url_type == "list":
        response = head_list(user_api_client)
    else:
        registration = RegistrationFactory()
        response = head_detail(user_api_client, pk=registration.pk)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
