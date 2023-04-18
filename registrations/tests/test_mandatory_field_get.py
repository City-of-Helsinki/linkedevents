import pytest
from rest_framework import status

from events.tests.conftest import APIClient
from events.tests.utils import get
from events.tests.utils import versioned_reverse as reverse
from registrations.models import MandatoryField

api_client = APIClient()

# === util methods ===
def get_list(api_client, data=None, query_string=None):
    url = reverse("mandatoryfield-list")
    if query_string:
        url = "%s?%s" % (url, query_string)
    return get(api_client, url, data=data)


def get_list_no_code_assert(api_client, data=None, query_string=None):
    url = reverse("mandatoryfield-list")
    if query_string:
        url = "%s?%s" % (url, query_string)
    return api_client.get(url, data=data, format="json")


def assert_mandatory_fields_in_response(
    expected_mandatory_field_ids, response, query=""
):
    mandatory_field_ids = {
        mandatory_field["id"] for mandatory_field in response.data["data"]
    }

    if query:
        assert mandatory_field_ids == expected_mandatory_field_ids, f"\nquery: {query}"
    else:
        assert mandatory_field_ids == expected_mandatory_field_ids


def get_list_and_assert_mandatory_fields(
    query: str, events: list, api_client: APIClient = api_client
):
    response = get_list(api_client, query_string=query)
    assert_mandatory_fields_in_response(events, response, query)


# === tests ===
@pytest.mark.django_db
def test_get_mandatory_field_list(api_client):
    get_list_and_assert_mandatory_fields(
        "",
        {
            MandatoryField.DefaultMandatoryField.CITY,
            MandatoryField.DefaultMandatoryField.NAME,
            MandatoryField.DefaultMandatoryField.PHONE_NUMBER,
            MandatoryField.DefaultMandatoryField.STREET_ADDRESS,
            MandatoryField.DefaultMandatoryField.ZIPCODE,
        },
    )
