import pytest

from events.tests.utils import versioned_reverse as reverse


def get_api_root(api_client):
    url = reverse("api-root")

    return api_client.get(url)


@pytest.mark.django_db
def test_return_correct_routes(api_client):
    response = get_api_root(api_client)
    assert response.data["keyword"] == "http://testserver/v1/keyword/"
    assert response.data["keyword_set"] == "http://testserver/v1/keyword_set/"
    assert response.data["place"] == "http://testserver/v1/place/"
    assert response.data["language"] == "http://testserver/v1/language/"
    assert response.data["organization"] == "http://testserver/v1/organization/"
    assert response.data["image"] == "http://testserver/v1/image/"
    assert response.data["event"] == "http://testserver/v1/event/"
    assert response.data["search"] == "http://testserver/v1/search/"
    assert response.data["user"] == "http://testserver/v1/user/"
    assert response.data["registration"] == "http://testserver/v1/registration/"
    assert response.data["signup"] == "http://testserver/v1/signup/"
    assert response.data.get("data_source") == None
    assert response.data.get("organization_class") == None
    assert response.data.get("feedback") == None
    assert response.data.get("guest-feedback") == None
