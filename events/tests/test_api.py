import pytest
from django.core.urlresolvers import reverse
from ..models import Event


@pytest.mark.django_db
def test_api_page_size(api_client, event):
    event_count = 200
    id_base = event.id
    for i in range(0, event_count):
        event.pk = "%s-%d" % (id_base, i)
        event.save(force_insert=True)
    resp = api_client.get(reverse('event-list') + '?page_size=10')
    assert resp.status_code == 200
    meta = resp.data['meta']
    assert meta['count'] == 201
    assert len(resp.data['data']) == 10

    resp = api_client.get(reverse('event-list') + '?page_size=1000')
    assert resp.status_code == 200
    meta = resp.data['meta']
    assert len(resp.data['data']) <= 100

