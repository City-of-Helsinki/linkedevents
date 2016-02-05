
import pytest
from .test_event_get import get_list, get_detail


@pytest.mark.django_db
def test__get_event_list_check_fields_exist(api_client, event):
    """
    Tests that event list endpoint returns the image as null.
    """
    response = get_list(api_client)
    assert(not response.data['data'][0]['image'])


@pytest.mark.django_db
def test__get_event_detail_check_fields_exist(api_client, event):
    """
    Tests that event detail endpoint returns the image as null.
    """
    response = get_detail(api_client, event.pk)
    assert(not response.data['image'])
