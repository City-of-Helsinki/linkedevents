from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model
from django_orghierarchy.models import Organization
from rest_framework import status, serializers
from rest_framework.test import APITestCase

from .utils import versioned_reverse as reverse
from ..api import get_authenticated_data_source_and_publisher, EventSerializer
from ..auth import ApiKeyAuth
from ..models import DataSource, Image


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


@pytest.mark.django_db
def test_get_authenticated_data_source_and_publisher(data_source):
    org = Organization.objects.create(
        data_source=data_source,
        origin_id='org-1',
        name='org-1',
    )
    data_source.owner = org
    data_source.save()

    request = MagicMock(auth=ApiKeyAuth(data_source))
    ds, publisher = get_authenticated_data_source_and_publisher(request)
    assert ds == data_source
    assert publisher == org


@pytest.mark.django_db
def test_serializer_validate_publisher():
    data_source = DataSource.objects.create(
        id='ds',
        name='data-source',
    )
    org_1 = Organization.objects.create(
        name='org-1',
        origin_id='org-1',
        data_source=data_source,
    )
    org_2 = Organization.objects.create(
        name='org-2',
        origin_id='org-2',
        data_source=data_source,
        replaced_by=org_1,
    )

    le_serializer = EventSerializer()
    le_serializer.publisher = org_2
    with pytest.raises(serializers.ValidationError):
        le_serializer.validate_publisher(org_2)


class TestImageAPI(APITestCase):

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create(username='testuser')

        self.data_source = DataSource.objects.create(
            id='ds',
            name='data-source',
            api_key="test_api_key",
            user_editable=True,
        )
        self.org_1 = Organization.objects.create(
            name='org-1',
            origin_id='org-1',
            data_source=self.data_source,
        )
        self.org_2 = Organization.objects.create(
            name='org-2',
            origin_id='org-2',
            data_source=self.data_source,
            replaced_by=self.org_1,
        )
        self.org_3 = Organization.objects.create(
            name='org-3',
            origin_id='org-3',
            data_source=self.data_source,
        )
        self.image_1 = Image.objects.create(
            name='image-1',
            data_source=self.data_source,
            publisher=self.org_1,
            url='http://fake.url/image-1/',
        )
        self.image_2 = Image.objects.create(
            name='image-2',
            data_source=self.data_source,
            publisher=self.org_2,
            url='http://fake.url/image-2/',
        )
        self.image_3 = Image.objects.create(
            name='image-2',
            data_source=self.data_source,
            publisher=self.org_3,
            url='http://fake.url/image-2/',
        )

    def test_get_image_list_with_publisher(self):
        # test filtering with replaced organization
        url = '{0}?publisher=ds:org-1'.format(reverse('image-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 2)

        # test filtering with organization that replaces organization
        url = '{0}?publisher=ds:org-2'.format(reverse('image-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 2)

        # test filtering with normal organization
        url = '{0}?publisher=ds:org-3'.format(reverse('image-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
