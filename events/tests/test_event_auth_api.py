from copy import deepcopy
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import override_settings
from django_orghierarchy.models import Organization
from rest_framework import status
from rest_framework.test import APITestCase

from .conftest import minimal_event_dict
from .utils import versioned_reverse as reverse
from ..models import DataSource, Event, Place, PublicationStatus


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
        self.org_4 = Organization.objects.create(
            name='org-4',
            origin_id='org-4',
            data_source=self.data_source,
            parent=self.org_1,
            internal_type=Organization.AFFILIATED
        )
        self.event_1 = Event.objects.create(
            id='ds:event-1',
            name='event-1',
            data_source=self.data_source,
            publisher=self.org_1,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_2 = Event.objects.create(
            id='ds:event-2',
            name='event-2',
            data_source=self.data_source,
            publisher=self.org_2,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_3 = Event.objects.create(
            id='ds:event-3',
            name='event-3',
            data_source=self.data_source,
            publisher=self.org_3,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_4 = Event.objects.create(
            id='ds:event-4',
            name='event-4',
            data_source=self.data_source,
            publisher=self.org_3,
            publication_status=PublicationStatus.PUBLIC,
        )
        self.event_5 = Event.objects.create(
            id='ds:event',
            name='event',
            data_source=self.data_source,
            publisher=self.org_4,
            publication_status=PublicationStatus.DRAFT
        )
        self.place = Place.objects.create(
            id='ds:place-1',
            name='place-1',
            data_source=self.data_source,
            publisher=self.org_1,
            position=Point(1, 1),
        )

    def test_event_list_with_auth_filters(self):
        # test with public request
        url = '{0}?show_all=1'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)  # event-4

        # test with authenticated data source and publisher
        self.org_2.admin_users.add(self.user)
        self.client.force_authenticate(self.user)
        url = '{0}?show_all=1'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Previously, the show_all filter only displayed drafts for one organization.
        # Descendants of organizations or replacement organizations were not considered at all.
        # Now, we display all drafts that the user has the right to view and edit.
        self.assertEqual(len(response.data['data']), 5)  # event-1, event-2, event-3, event-4 and event-5

    def test_event_list_with_publisher_filters(self):
        # test with public request
        url = '{0}?show_all=1&publisher=ds:org-3'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)  # event-4

        # test with authenticated data source and publisher
        self.org_2.admin_users.add(self.user)
        self.client.force_authenticate(self.user)
        url = '{0}?show_all=1&publisher=ds:org-2'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # note that org-2 is replaced by org-1
        # with publisher filter, we only display drafts for that organization.
        # Replacements are considered, but descendants are not.
        self.assertEqual(len(response.data['data']), 2)  # event-1 and event-2

    def test_bulk_destroy(self):
        url = reverse('event-list')
        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_unauthenticated_user_get_public_event(self):
        url = reverse('event-detail', kwargs={'pk': self.event_4.id})

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('publication_status', response.data)

    def test_unauthenticated_user_get_draft_event_not_found(self):
        url = reverse('event-detail', kwargs={'pk': self.event_1.id})

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_create_event_denied(self):
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_user_update_public_event_denied(self):
        url = reverse('event-detail', kwargs={'pk': self.event_4.id})
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = minimal_event_dict(self.data_source, self.org_3, location_id)

        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_user_delete_public_event_denied(self):
        url = reverse('event-detail', kwargs={'pk': self.event_4.id})

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_random_user_get_public_event(self):
        url = reverse('event-detail', kwargs={'pk': self.event_4.id})

        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('publication_status', response.data)

    def test_random_user_get_draft_event_not_found(self):
        url = reverse('event-detail', kwargs={'pk': self.event_1.id})

        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_random_user_create_event_denied(self):
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_random_user_update_public_event_denied(self):
        url = reverse('event-detail', kwargs={'pk': self.event_4.id})
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = minimal_event_dict(self.data_source, self.org_3, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_random_user_delete_public_event_denied(self):
        url = reverse('event-detail', kwargs={'pk': self.event_4.id})

        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_random_user_bulk_create(self):
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data_1 = minimal_event_dict(self.data_source, self.org_1, location_id)
        data_1['name']['fi'] = 'event-data-1'
        data_2 = deepcopy(data_1)
        data_2['name']['fi'] = 'event-data-2'

        self.client.force_authenticate(self.user)
        response = self.client.post(url, [data_1, data_2], format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_random_user_bulk_update(self):
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.put(url, [data], format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_create_event(self):
        self.org_1.admin_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_update_event(self):
        self.org_1.admin_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

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

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_410_GONE)

    def test_admin_delete_sub_organization_event(self):
        self.org_1.admin_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_3.id})
        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_410_GONE)

    def test_admin_update_sub_organization_event(self):
        self.org_1.admin_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

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

        url = reverse('event-detail', kwargs={'pk': self.event_5.id})
        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_410_GONE)

    def test_admin_update_affiliated_organization_event(self):
        self.org_1.admin_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_5.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)
        data['publication_status'] = 'public'
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event_5.refresh_from_db()
        self.assertEqual(self.event_5.publication_status, PublicationStatus.PUBLIC)

    def test_admin_bulk_create(self):
        self.org_1.admin_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data_1 = minimal_event_dict(self.data_source, self.org_1, location_id)
        data_1['name']['fi'] = 'event-data-1'
        data_1['publication_status'] = 'public'
        data_2 = deepcopy(data_1)
        data_2['name']['fi'] = 'event-data-2'
        data_2['publication_status'] = 'draft'

        self.client.force_authenticate(self.user)
        response = self.client.post(url, [data_1, data_2], format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        qs = Event.objects.filter(name_fi__in=['event-data-1', 'event-data-2'])
        self.assertEqual(qs.count(), 2)

    @override_settings(SYSTEM_DATA_SOURCE_ID='ds')
    def test_admin_bulk_update(self):
        self.org_1.admin_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data_1 = minimal_event_dict(self.data_source, self.org_1, location_id)
        data_1['id'] = self.event_1.id  # own event
        data_1['name']['fi'] = 'event-1-changed'
        data_2 = deepcopy(data_1)
        data_2['id'] = self.event_3.id  # sub-organization event
        data_2['name']['fi'] = 'event-3-changed'
        data_3 = deepcopy(data_1)
        data_3['id'] = self.event_5.id  # affiliated organization event
        data_3['name']['fi'] = 'event-5-changed'

        self.client.force_authenticate(self.user)
        response = self.client.put(url, [data_1, data_2, data_3], format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event_1.refresh_from_db()
        self.assertEqual(self.event_1.name_fi, 'event-1-changed')

        self.event_3.refresh_from_db()
        self.assertEqual(self.event_3.name_fi, 'event-3-changed')

        self.event_5.refresh_from_db()
        self.assertEqual(self.event_5.name_fi, 'event-5-changed')

    def test_regular_user_create_public_event_denied(self):
        self.org_1.regular_users.add(self.user)

        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_update_public_event_denied(self):
        self.org_1.regular_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_4.id})
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_delete_public_event_denied(self):
        self.org_3.regular_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_4.id})

        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_create_draft_event(self):
        self.org_1.regular_users.add(self.user)

        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = minimal_event_dict(self.data_source, self.org_1, location_id)
        data['publication_status'] = 'draft'

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_regular_user_update_draft_event_other_fields(self):
        self.org_3.regular_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_3.id})
        data = minimal_event_dict(self.data_source, self.org_3, location_id)
        data['publication_status'] = 'draft'
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_regular_user_update_draft_event_to_public_denied(self):
        self.org_3.regular_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_3.id})
        data = minimal_event_dict(self.data_source, self.org_3, location_id)
        data['publication_status'] = 'public'
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_delete_draft_event(self):
        self.org_3.regular_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_3.id})
        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_410_GONE)

    def test_regular_user_cannot_find_sub_organization_draft_event(self):
        self.org_1.regular_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_3.id})
        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_regular_user_cannot_find_affiliated_organization_draft_event(self):
        self.org_1.regular_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_5.id})
        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_regular_user_bulk_create(self):
        self.org_1.regular_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data_1 = minimal_event_dict(self.data_source, self.org_1, location_id)
        data_1['name']['fi'] = 'event-data-1'
        data_1['publication_status'] = 'public'
        data_2 = deepcopy(data_1)
        data_2['name']['fi'] = 'event-data-2'
        data_2['publication_status'] = 'draft'

        self.client.force_authenticate(self.user)
        response = self.client.post(url, [data_1, data_2], format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # test creating multiple draft events
        data_1['publication_status'] = 'draft'
        self.client.force_authenticate(self.user)
        response = self.client.post(url, [data_1, data_2], format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        qs = Event.objects.filter(name_fi__in=['event-data-1', 'event-data-2'])
        self.assertEqual(qs.count(), 2)

    @override_settings(SYSTEM_DATA_SOURCE_ID='ds')
    def test_regular_user_bulk_update(self):
        self.org_3.regular_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data_1 = minimal_event_dict(self.data_source, self.org_3, location_id)
        data_1['id'] = self.event_3.id  # own event
        data_1['name']['fi'] = 'event-3-changed'
        data_1['publication_status'] = 'draft'
        data_2 = deepcopy(data_1)
        data_2['id'] = self.event_4.id  # public event
        data_2['name']['fi'] = 'event-4-changed'
        data_2['publication_status'] = 'public'

        self.client.force_authenticate(self.user)
        response = self.client.put(url, [data_1, data_2], format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        data_2['publication_status'] = 'draft'
        response = self.client.put(url, [data_1, data_2], format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data[0], 'Could not find all objects to update.')

        response = self.client.put(url, [data_1], format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.event_3.refresh_from_db()
        self.assertEqual(self.event_3.name, 'event-3-changed')
        self.assertEqual(self.event_3.publication_status, PublicationStatus.DRAFT)
