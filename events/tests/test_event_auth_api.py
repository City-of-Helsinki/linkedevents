from copy import deepcopy

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import override_settings
from django_orghierarchy.models import Organization
from rest_framework import status
from rest_framework.test import APITestCase
import pytest

from .utils import versioned_reverse as reverse
from ..models import DataSource, Event, Place, PublicationStatus


@pytest.mark.usefixtures("make_complex_event_dict_class", "make_minimal_event_dict_class", "languages_class")
class TestEventAPI(APITestCase):

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create(username='testuser')

        # this is the default data source when users POST through API
        self.system_data_source = DataSource.objects.create(
            id='ds',
            name='data-source',
            api_key="test_api_key",
            user_editable=True,
        )
        # this is a data source that only allows POST with api_key (external systems), but users may still PUT
        self.editable_data_source = DataSource.objects.create(
            id='eds',
            name='editable-data-source',
            api_key="test_api_key_2",
            user_editable=True,
        )
        # this is a data source that only allows POST and PUT with api_key (external systems)
        self.non_editable_data_source = DataSource.objects.create(
            id='neds',
            name='non-editable-data-source',
            api_key="test_api_key_3",
            user_editable=False,
        )
        # this is a data source that only allows POST with api_key (external systems), but users may still PUT
        self.external_editable_data_source = DataSource.objects.create(
            id='eeds',
            name='external-editable-data-source',
            api_key="test_api_key_4",
            user_editable=True,
        )
        self.org_1 = Organization.objects.create(
            name='org-1',
            origin_id='org-1',
            data_source=self.non_editable_data_source,
        )
        # org_1 owns most data sources
        self.org_1.owned_systems.add(self.system_data_source,
                                     self.editable_data_source,
                                     self.non_editable_data_source)
        self.org_2 = Organization.objects.create(
            name='org-2',
            origin_id='org-2',
            data_source=self.non_editable_data_source,
            replaced_by=self.org_1,
        )
        self.org_3 = Organization.objects.create(
            name='org-3',
            origin_id='org-3',
            data_source=self.non_editable_data_source,
            parent=self.org_1,
        )
        self.org_4 = Organization.objects.create(
            name='org-4',
            origin_id='org-4',
            data_source=self.non_editable_data_source,
            parent=self.org_1,
            internal_type=Organization.AFFILIATED
        )
        self.org_5 = Organization.objects.create(
            name='org-5',
            origin_id='org-5',
            data_source=self.non_editable_data_source,
        )
        # org_5 owns the external data source
        self.org_5.owned_systems.add(self.external_editable_data_source)

        self.event_1 = Event.objects.create(
            id='ds:event-1',
            name='event-1',
            data_source=self.system_data_source,
            publisher=self.org_1,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_2 = Event.objects.create(
            id='ds:event-2',
            name='event-2',
            data_source=self.system_data_source,
            publisher=self.org_2,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_3 = Event.objects.create(
            id='ds:event-3',
            name='event-3',
            data_source=self.system_data_source,
            publisher=self.org_3,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_4 = Event.objects.create(
            id='ds:event-4',
            name='event-4',
            data_source=self.system_data_source,
            publisher=self.org_3,
            publication_status=PublicationStatus.PUBLIC,
        )
        self.event_5 = Event.objects.create(
            id='ds:event-5',
            name='event-5',
            data_source=self.system_data_source,
            publisher=self.org_4,
            publication_status=PublicationStatus.DRAFT,
        )
        self.event_6 = Event.objects.create(
            id='ds:event-6',
            name='event-6',
            data_source=self.system_data_source,
            publisher=self.org_5,
            publication_status=PublicationStatus.PUBLIC,
        )
        self.event_7 = Event.objects.create(
            id='eds:event-7',
            name='event-7',
            data_source=self.editable_data_source,
            publisher=self.org_1,
            publication_status=PublicationStatus.PUBLIC,
        )
        self.event_8 = Event.objects.create(
            id='neds:event-8',
            name='event-8',
            data_source=self.non_editable_data_source,
            publisher=self.org_1,
            publication_status=PublicationStatus.PUBLIC,
        )
        self.event_9 = Event.objects.create(
            id='eeds:event-9',
            name='event-9',
            data_source=self.external_editable_data_source,
            publisher=self.org_5,
            publication_status=PublicationStatus.PUBLIC,
        )
        self.place = Place.objects.create(
            id='neds:place-1',
            name='place-1',
            data_source=self.non_editable_data_source,
            publisher=self.org_1,
            position=Point(1, 1),
        )

    def test_event_list_with_show_all_filter(self):
        # test with public request
        url = '{0}?show_all=1'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 5)  # event-4, event-6, event-7, event-8 and event-9
        for event in response.data['data']:
            self.assertNotIn('publication_status', event)
            self.assertNotIn('created_by', event)
            self.assertNotIn('last_modified_by', event)

        # test with authenticated data source and *replaced* publisher organization
        self.org_2.admin_users.add(self.user)
        self.client.force_authenticate(self.user)
        url = '{0}?show_all=1'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Previously, the show_all filter only displayed drafts for one organization.
        # Descendants of organizations or replacement organizations were not considered at all.
        # Now, we display all events and drafts that the user has the right to view and edit.
        self.assertEqual(len(response.data['data']), 9)  # all 8 events
        for event in response.data['data']:
            self.assertIn('publication_status', event)
            # user name fields should be shown in all except event-6 and event-9
            if event['id'] == 'ds:event-6' or event['id'] == 'eeds:event-9':
                self.assertNotIn('created_by', event)
                self.assertNotIn('last_modified_by', event)
            else:
                self.assertIn('created_by', event)
                self.assertIn('last_modified_by', event)

    def test_event_list_with_admin_user_filter(self):
        # test with public request
        url = '{0}?admin_user=true'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 0)  # public users are not admins

        # test with authenticated data source and *replaced* publisher organization
        self.org_2.admin_users.add(self.user)
        self.client.force_authenticate(self.user)
        url = '{0}?admin_user=true'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # We should see everything else but not public events outside the admin orgs
        self.assertEqual(len(response.data['data']), 7)  # all except event-6
        for event in response.data['data']:
            self.assertIn('publication_status', event)
            # now we should only have events with admin rights
            self.assertIn('created_by', event)
            self.assertIn('last_modified_by', event)

    @override_settings(SYSTEM_DATA_SOURCE_ID='ds')
    def test_event_list_with_created_by_filter(self):
        # test with public request
        url = '{0}?created_by=me'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 0)  # public users haven't created events

        # create event with admin user
        self.org_1.admin_users.add(self.user)
        self.client.force_authenticate(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = self.make_complex_event_dict(self.system_data_source, self.org_1, location_id, self.languages)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # test with admin user
        url = '{0}?created_by=me'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # We should only see the event created by us
        self.assertEqual(len(response.data['data']), 1)
        for event in response.data['data']:
            self.assertIn('publication_status', event)
            # now we should only have events with admin rights
            self.assertIn('created_by', event)
            self.assertIn('last_modified_by', event)

    def test_event_list_with_publisher_filters(self):
        # test with public request
        url = '{0}?show_all=1&publisher=neds:org-3'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)  # event-4
        url = '{0}?admin_user=1&publisher=neds:org-3'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 0)  # public users are not admins

        # test with authenticated data source and publisher
        self.org_2.admin_users.add(self.user)
        self.client.force_authenticate(self.user)
        url = '{0}?show_all=1&publisher=neds:org-2'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # note that org-2 is replaced by org-1
        # with publisher filter, we only display drafts and public events for that organization.
        # Replacements are considered, but descendants are not.
        self.assertEqual(len(response.data['data']), 4)  # event-1, event-2, event-7 and event-8
        for event in response.data['data']:
            self.assertIn('publication_status', event)
            # now we should only have events with admin rights
            self.assertIn('created_by', event)
            self.assertIn('last_modified_by', event)

        url = '{0}?admin_user=1&publisher=neds:org-2'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # note that org-2 is replaced by org-1
        # with publisher filter, we only display drafts and public events for that organization.
        # Replacements are considered, but descendants are not.
        self.assertEqual(len(response.data['data']), 4)  # event-1, event-2, event-7 and event-8
        for event in response.data['data']:
            self.assertIn('publication_status', event)
            # now we should only have events with admin rights
            self.assertIn('created_by', event)
            self.assertIn('last_modified_by', event)
        url = '{0}?admin_user=1&publisher=neds:org-1'.format(reverse('event-list'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # with publisher filter, we only display drafts and public events for that organization.
        # Replacements are considered, but descendants are not.
        self.assertEqual(len(response.data['data']), 4)  # event-1, event-2, event-7 and event-8
        for event in response.data['data']:
            self.assertIn('publication_status', event)
            # now we should only have events with admin rights
            self.assertIn('created_by', event)
            self.assertIn('last_modified_by', event)

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
        self.assertNotIn('created_by', response.data)
        self.assertNotIn('last_modified_by', response.data)

    def test_unauthenticated_user_get_draft_event_not_found(self):
        url = reverse('event-detail', kwargs={'pk': self.event_1.id})

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_create_event_denied(self):
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = self.make_minimal_event_dict(self.system_data_source, self.org_1, location_id)

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_user_update_public_event_denied(self):
        url = reverse('event-detail', kwargs={'pk': self.event_4.id})
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = self.make_minimal_event_dict(self.system_data_source, self.org_3, location_id)

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
        self.assertNotIn('created_by', response.data)
        self.assertNotIn('last_modified_by', response.data)

    def test_random_user_get_draft_event_not_found(self):
        url = reverse('event-detail', kwargs={'pk': self.event_1.id})

        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_random_user_create_event_denied(self):
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = self.make_minimal_event_dict(self.system_data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_random_user_update_public_event_denied(self):
        url = reverse('event-detail', kwargs={'pk': self.event_4.id})
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = self.make_minimal_event_dict(self.system_data_source, self.org_3, location_id)

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
        data_1 = self.make_complex_event_dict(self.system_data_source, self.org_1, location_id, self.languages)
        data_1['name']['fi'] = 'event-data-1'
        data_2 = deepcopy(data_1)
        data_2['name']['fi'] = 'event-data-2'

        self.client.force_authenticate(self.user)
        response = self.client.post(url, [data_1, data_2], format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_random_user_bulk_update(self):
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = self.make_complex_event_dict(self.system_data_source, self.org_1, location_id, self.languages)

        self.client.force_authenticate(self.user)
        response = self.client.put(url, [data], format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_get_own_public_event(self):
        self.org_1.admin_users.add(self.user)
        url = reverse('event-detail', kwargs={'pk': self.event_4.id})

        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('publication_status', response.data)
        self.assertIn('created_by', response.data)
        self.assertIn('last_modified_by', response.data)

    def test_admin_get_other_public_event(self):
        self.org_1.admin_users.add(self.user)
        url = reverse('event-detail', kwargs={'pk': self.event_6.id})

        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('publication_status', response.data)
        self.assertNotIn('created_by', response.data)
        self.assertNotIn('last_modified_by', response.data)

    def test_affiliated_organization_admin_get_own_public_event(self):
        # only proper (not affiliated) admins should see user names!
        self.org_4.admin_users.add(self.user)
        url = reverse('event-detail', kwargs={'pk': self.event_4.id})

        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('publication_status', response.data)
        self.assertNotIn('created_by', response.data)
        self.assertNotIn('last_modified_by', response.data)

    @override_settings(SYSTEM_DATA_SOURCE_ID='ds')
    def test_admin_create_event(self):
        self.org_1.admin_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = self.make_complex_event_dict(self.system_data_source, self.org_1, location_id, self.languages)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('publication_status', response.data)
        self.assertIn('created_by', response.data)
        self.assertIn('last_modified_by', response.data)

    def test_admin_update_event(self):
        self.org_1.admin_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_1.id})
        data = self.make_complex_event_dict(self.system_data_source, self.org_1, location_id, self.languages)
        data['publication_status'] = 'public'
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('publication_status', response.data)
        self.assertIn('created_by', response.data)
        self.assertIn('last_modified_by', response.data)

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
        data = self.make_complex_event_dict(self.system_data_source, self.org_3, location_id, self.languages)
        data['publication_status'] = 'public'
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('publication_status', response.data)
        self.assertIn('created_by', response.data)
        self.assertIn('last_modified_by', response.data)

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
        data = self.make_complex_event_dict(self.system_data_source, self.org_4, location_id, self.languages)
        data['publication_status'] = 'public'
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('publication_status', response.data)
        self.assertIn('created_by', response.data)
        self.assertIn('last_modified_by', response.data)

        self.event_5.refresh_from_db()
        self.assertEqual(self.event_5.publication_status, PublicationStatus.PUBLIC)

    @override_settings(SYSTEM_DATA_SOURCE_ID='ds')
    def test_admin_bulk_create(self):
        self.org_1.admin_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data_1 = self.make_complex_event_dict(self.system_data_source, self.org_1, location_id, self.languages)
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
        self.org_5.admin_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data_1 = self.make_complex_event_dict(self.system_data_source, self.org_1, location_id, self.languages)
        data_1['id'] = self.event_1.id  # own event
        data_1['name']['fi'] = 'event-1-changed'
        data_2 = deepcopy(data_1)
        data_2['id'] = self.event_3.id  # sub-organization event
        data_2['name']['fi'] = 'event-3-changed'
        data_2['publisher'] = self.org_3.id
        data_3 = deepcopy(data_1)
        data_3['id'] = self.event_5.id  # affiliated organization event
        data_3['name']['fi'] = 'event-5-changed'
        data_3['publisher'] = self.org_4.id
        data_4 = deepcopy(data_1)
        data_4['id'] = self.event_7.id  # editable datasource event
        data_4['name']['fi'] = 'event-7-changed'
        data_4['publisher'] = self.org_1.id
        data_4['data_source'] = self.editable_data_source.id
        data_5 = deepcopy(data_1)
        data_5['id'] = self.event_9.id  # external editable datasource event
        data_5['name']['fi'] = 'event-9-changed'
        data_5['publisher'] = self.org_5.id
        data_5['data_source'] = self.external_editable_data_source.id

        self.client.force_authenticate(self.user)
        response = self.client.put(url, [data_1, data_2, data_3, data_4, data_5], format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event_1.refresh_from_db()
        self.assertEqual(self.event_1.name_fi, 'event-1-changed')

        self.event_3.refresh_from_db()
        self.assertEqual(self.event_3.name_fi, 'event-3-changed')

        self.event_5.refresh_from_db()
        self.assertEqual(self.event_5.name_fi, 'event-5-changed')

        self.event_7.refresh_from_db()
        self.assertEqual(self.event_7.name_fi, 'event-7-changed')

        self.event_9.refresh_from_db()
        self.assertEqual(self.event_9.name_fi, 'event-9-changed')

    def test_admin_create_spoof_editable_data_source_denied(self):
        self.org_5.admin_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        # here, we are trying to use a non-system data source NOT owned by org
        data = self.make_complex_event_dict(self.editable_data_source, self.org_5, location_id, self.languages)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_create_editable_data_source_denied(self):
        self.org_1.admin_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        # here, we are trying to use a non-system data source owned by org to POST as user
        data = self.make_complex_event_dict(self.editable_data_source, self.org_1, location_id, self.languages)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_key_create_editable_data_source_allowed(self):
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        # here, we are trying to use a non-system data source owned by org to POST with api key
        data = self.make_complex_event_dict(self.editable_data_source, self.org_1, location_id, self.languages)

        self.client.credentials(apikey=self.editable_data_source.api_key)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_create_non_editable_data_source_denied(self):
        self.org_1.admin_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        # here, the data source does not allow user edits
        data = self.make_complex_event_dict(self.non_editable_data_source, self.org_1, location_id, self.languages)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_key_create_non_editable_data_source_allowed(self):
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        # here, the data source does not allow user edits, but it has api key
        data = self.make_complex_event_dict(self.non_editable_data_source, self.org_1, location_id, self.languages)

        self.client.credentials(apikey=self.non_editable_data_source.api_key)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_update_spoof_data_source_denied(self):
        self.org_5.admin_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_6.id})
        # here, we are trying to use a non-system data source NOT owned by org
        data = self.make_complex_event_dict(self.editable_data_source, self.org_5, location_id, self.languages)
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.event_1.refresh_from_db()
        self.assertEqual(self.event_6.data_source, self.system_data_source)

    def test_admin_update_change_data_source_denied(self):
        self.org_1.admin_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_1.id})
        # here, we are trying to use a non-system data source that IS owned by org
        data = self.make_complex_event_dict(self.editable_data_source, self.org_1, location_id, self.languages)
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.event_1.refresh_from_db()
        self.assertEqual(self.event_1.data_source, self.system_data_source)

    def test_admin_update_system_data_source_allowed(self):
        self.org_1.admin_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_1.id})
        # here, we are just editing the event without changing the data source
        data = self.make_complex_event_dict(self.system_data_source, self.org_1, location_id, self.languages)
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event_1.refresh_from_db()
        self.assertEqual(self.event_1.data_source, self.system_data_source)

    def test_admin_update_editable_data_source_allowed(self):
        self.org_1.admin_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_7.id})
        # here, we are just editing the event without changing the data source
        data = self.make_complex_event_dict(self.editable_data_source, self.org_1, location_id, self.languages)
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event_7.refresh_from_db()
        self.assertEqual(self.event_7.data_source, self.editable_data_source)

    def test_admin_update_non_editable_data_source_denied(self):
        self.org_1.admin_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_8.id})
        # here, we are just editing the event, but the data source does not allow user edits
        data = self.make_complex_event_dict(self.non_editable_data_source, self.org_1, location_id, self.languages)
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.event_8.refresh_from_db()
        self.assertEqual(self.event_8.data_source, self.non_editable_data_source)

    def test_api_key_update_non_editable_data_source_allowed(self):
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_8.id})
        # here, the data source does not allow user edits, but it has api key
        data = self.make_complex_event_dict(self.non_editable_data_source, self.org_1, location_id, self.languages)
        self.client.credentials(apikey=self.non_editable_data_source.api_key)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.event_8.refresh_from_db()
        self.assertEqual(self.event_8.data_source, self.non_editable_data_source)

    def test_regular_user_create_public_event_denied(self):
        self.org_1.regular_users.add(self.user)

        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = self.make_minimal_event_dict(self.system_data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_update_public_event_denied(self):
        self.org_1.regular_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_4.id})
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = self.make_minimal_event_dict(self.system_data_source, self.org_1, location_id)

        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_delete_public_event_denied(self):
        self.org_3.regular_users.add(self.user)

        url = reverse('event-detail', kwargs={'pk': self.event_4.id})

        self.client.force_authenticate(self.user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(SYSTEM_DATA_SOURCE_ID='ds')
    def test_regular_user_create_draft_event(self):
        self.org_1.regular_users.add(self.user)

        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data = self.make_complex_event_dict(self.system_data_source, self.org_1, location_id, self.languages)
        data['publication_status'] = 'draft'

        self.client.force_authenticate(self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # regular users should not see usernames
        self.assertIn('publication_status', response.data)
        self.assertNotIn('created_by', response.data)
        self.assertNotIn('last_modified_by', response.data)

    def test_regular_user_update_draft_event_other_fields(self):
        self.org_3.regular_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_3.id})
        data = self.make_complex_event_dict(self.system_data_source, self.org_3, location_id, self.languages)
        data['publication_status'] = 'draft'
        self.client.force_authenticate(self.user)
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('publication_status', response.data)
        # regular users should not see usernames
        self.assertNotIn('created_by', response.data)
        self.assertNotIn('last_modified_by', response.data)

    def test_regular_user_update_draft_event_to_public_denied(self):
        self.org_3.regular_users.add(self.user)
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})

        url = reverse('event-detail', kwargs={'pk': self.event_3.id})
        data = self.make_minimal_event_dict(self.system_data_source, self.org_3, location_id)
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

    @override_settings(SYSTEM_DATA_SOURCE_ID='ds')
    def test_regular_user_bulk_create(self):
        self.org_1.regular_users.add(self.user)
        url = reverse('event-list')
        location_id = reverse('place-detail', kwargs={'pk': self.place.id})
        data_1 = self.make_complex_event_dict(self.system_data_source, self.org_1, location_id, self.languages)
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
        data_1 = self.make_complex_event_dict(self.system_data_source, self.org_3, location_id, self.languages)
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
