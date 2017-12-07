from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django_orghierarchy.models import Organization
from rest_framework import status, serializers
from rest_framework.test import APITestCase

from .conftest import minimal_event_dict
from .utils import versioned_reverse as reverse
from ..api import get_authenticated_data_source_and_publisher, EventSerializer
from ..auth import ApiKeyAuth
from ..models import DataSource, Event, Image, Place, PublicationStatus


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


class TestEventAPI(APITestCase):

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
            parent=self.org_1,
        )
        self.event_1 = Event.objects.create(
            id='event-1',
            name='event-1',
            data_source=self.data_source,
            publisher=self.org_1,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_2 = Event.objects.create(
            id='event-2',
            name='event-2',
            data_source=self.data_source,
            publisher=self.org_2,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_3 = Event.objects.create(
            id='event-3',
            name='event-3',
            data_source=self.data_source,
            publisher=self.org_3,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_4 = Event.objects.create(
            id='event-4',
            name='event-4',
            data_source=self.data_source,
            publisher=self.org_3,
            publication_status=PublicationStatus.PUBLIC,
        )

    def test_event_list_with_auth_filters(self):
        # test with public request
        url = '{0}?show_all=1'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)  # event-4

        # test with authenticated data source and publisher
        with patch(
            'events.api.get_authenticated_data_source_and_publisher',
            MagicMock(return_value=(self.data_source, self.org_2))
        ):
            url = '{0}?show_all=1'.format(reverse('event-list'))
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data['data']), 3)  # event-1, event-2 and event-4

    def test_event_list_with_publisher_filters(self):
        # test with public request
        url = '{0}?show_all=1&publisher=ds:org-3'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)  # event-4

        # test with authenticated data source and publisher
        with patch(
            'events.api.get_authenticated_data_source_and_publisher',
            MagicMock(return_value=(self.data_source, self.org_2))
        ):
            url = '{0}?show_all=1&publisher=ds:org-2'.format(reverse('event-list'))
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # note that org-2 is replaced by org-1
            self.assertEqual(len(response.data['data']), 2)  # event-1 and event-2

    def test_random_user_get_draft_event_not_found(self):
        url = reverse('event-detail', kwargs={'pk': self.event_1.id})

        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_random_user_create_event_denied(self):
        place = Place.objects.create(
            id='ds:place-1',
            name='place-1',
            data_source=self.data_source,
            publisher=self.org_1,
            position=Point(1, 1),
        )

        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_random_user_update_public_event_denied(self):
        place = Place.objects.create(
            id='ds:place-1',
            name='place-1',
            data_source=self.data_source,
            publisher=self.org_1,
            position=Point(1, 1),
        )

        url = reverse('event-detail', kwargs={'pk': self.event_4.id})
        location_id = reverse('place-detail', kwargs={'pk': place.id})
        data = minimal_event_dict(self.data_source, self.org_3, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_random_user_delete_public_event_denied(self):
        url = reverse('event-detail', kwargs={'pk': self.event_4.id})

        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_create_event(self):
        self.org_1.admin_users.add(self.user)
        place = Place.objects.create(
            id='ds:place-1',
            name='place-1',
            data_source=self.data_source,
            publisher=self.org_1,
            position=Point(1, 1),
        )

        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_update_event(self):
        self.org_1.admin_users.add(self.user)
        place = Place.objects.create(
            id='ds:place-1',
            name='place-1',
            data_source=self.data_source,
            publisher=self.org_1,
            position=Point(1, 1),
        )
        location_id = reverse('place-detail', kwargs={'pk': place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_1.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)
        data['publication_status'] = 'public'
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event_1.refresh_from_db()
        self.assertEqual(self.event_1.publication_status, PublicationStatus.PUBLIC)

    def test_admin_delete_event(self):
        self.org_1.admin_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_1.id})
        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_delete_sub_organization_event(self):
        self.org_1.admin_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_3.id})
        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_update_sub_organization_event(self):
        self.org_1.admin_users.add(self.user)
        place = Place.objects.create(
            id='ds:place-1',
            name='place-1',
            data_source=self.data_source,
            publisher=self.org_1,
            position=Point(1, 1),
        )
        location_id = reverse('place-detail', kwargs={'pk': place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_3.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)
        data['publication_status'] = 'public'
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event_3.refresh_from_db()
        self.assertEqual(self.event_3.publication_status, PublicationStatus.PUBLIC)

    def test_admin_delete_affiliated_organization_event(self):
        self.org_1.admin_users.add(self.user)
        org = Organization.objects.create(
            name='affiliated-org',
            origin_id='affiliated-org',
            data_source=self.data_source,
            responsible_organization=self.org_1
        )
        event = Event.objects.create(
            id='event',
            name='event',
            data_source=self.data_source,
            publisher=org,
            publication_status=PublicationStatus.DRAFT
        )

        url = reverse('event-detail', kwargs={'pk': event.id})
        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_update_affiliated_organization_event(self):
        self.org_1.admin_users.add(self.user)
        org = Organization.objects.create(
            name='affiliated-org',
            origin_id='affiliated-org',
            data_source=self.data_source,
            responsible_organization=self.org_1
        )
        event = Event.objects.create(
            id='event',
            name='event',
            data_source=self.data_source,
            publisher=org,
            publication_status=PublicationStatus.DRAFT
        )
        place = Place.objects.create(
            id='ds:place-1',
            name='place-1',
            data_source=self.data_source,
            publisher=self.org_1,
            position=Point(1, 1),
        )
        location_id = reverse('place-detail', kwargs={'pk': place.id})

        url = reverse('event-detail', kwargs={'pk': event.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)
        data['publication_status'] = 'public'
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event.refresh_from_db()
        self.assertEqual(event.publication_status, PublicationStatus.PUBLIC)

    def test_regular_user_create_public_event_denied(self):
        self.org_1.regular_users.add(self.user)
        place = Place.objects.create(
            id='ds:place-1',
            name='place-1',
            data_source=self.data_source,
            publisher=self.org_1,
            position=Point(1, 1),
        )

        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_update_public_event_denied(self):
        self.org_1.regular_users.add(self.user)
        place = Place.objects.create(
            id='ds:place-1',
            name='place-1',
            data_source=self.data_source,
            publisher=self.org_1,
            position=Point(1, 1),
        )

        url = reverse('event-detail', kwargs={'pk': self.event_4.id})
        location_id = reverse('place-detail', kwargs={'pk': place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_delete_public_event_denied(self):
        self.org_1.regular_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_4.id})

        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_create_draft_event(self):
        self.org_1.regular_users.add(self.user)
        place = Place.objects.create(
            id='ds:place-1',
            name='place-1',
            data_source=self.data_source,
            publisher=self.org_1,
            position=Point(1, 1),
        )

        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)
        data['publication_status'] = 'draft'

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_regular_user_cannot_find_sub_organization_draft_event(self):
        self.org_1.regular_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_3.id})
        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_regular_user_cannot_find_affiliated_organization_draft_event(self):
        self.org_1.regular_users.add(self.user)
        org = Organization.objects.create(
            name='affiliated-org',
            origin_id='affiliated-org',
            data_source=self.data_source,
            responsible_organization=self.org_1
        )
        event = Event.objects.create(
            id='event',
            name='event',
            data_source=self.data_source,
            publisher=org,
            publication_status=PublicationStatus.DRAFT
        )

        url = reverse('event-detail', kwargs={'pk': event.id})
        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
