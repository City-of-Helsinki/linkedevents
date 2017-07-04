import pytest
from .utils import versioned_reverse as reverse


@pytest.mark.django_db
def test_docx_renderer(api_client, event, place):
    event.description_en = "Test event English description"
    event.name_en = "Test event English name"
    event.headline = "Test event headline"
    event.save()

    response = api_client.get(
        reverse('event-list') + '?format=docx&location=%s' % (
            place.id.replace(' ', '%20')
        )
    )
    assert response.status_code == 200
