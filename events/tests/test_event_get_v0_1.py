
import pytest
from .test_event_get import get_list, get_detail

# Module globals for py.test fixtures
version = "v0.1"


@pytest.mark.django_db
def test__get_event_list_check_fields_exist(api_client, event):
    """
    Tests that event list endpoint returns the image as null.
    """
    response = get_list(api_client, version='v0.1')
    assert (not response.data['data'][0]['image'])


@pytest.mark.django_db
def test__get_event_detail_check_fields_exist(api_client, event):
    """
    Tests that event detail endpoint returns the image as null.
    """
    response = get_detail(api_client, event.pk, version='v0.1')
    assert (not response.data['image'])


@pytest.mark.django_db
def test__api_get_event_list_check_fields_exist(api_get_list):
    """
    Tests that event list endpoint returns the image as null.

    TODO: Testing how tests should/could be structured
    This one sets version on module level and does not deal with API client
    """
    response = api_get_list()
    assert (not response.data['data'][0]['image'])
