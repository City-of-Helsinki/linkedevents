# -*- coding: utf-8 -*-
import pytest

from events.tests.utils import versioned_reverse as reverse
from django_orghierarchy.models import Organization

@pytest.mark.django_db
def test_get_organization_class(user, organization, api_client):
    url = reverse('organizationclass-list')
    api_client.force_authenticate(user)

    response = api_client.get(url, format='json')
    response.status_code == 200


@pytest.mark.django_db
def test_post_no_parent(user, organization, data_source, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user)

    payload = {'data_source': data_source.id,
            'id': data_source.id + 'test_organization2',
            'origin_id': 'test_organization2',
            'name': 'test org'
    }
    
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 201
    assert response.data['name'] == payload['name']


@pytest.mark.django_db
def test_post_existing_id_fails(user, organization, data_source, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user)

    payload = {'data_source': data_source.id,
            'id': organization.id,
            'origin_id': 'test_organization2',
            'name': 'test org'
    }
    
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 403


@pytest.mark.django_db
def test_post_parent_user_has_rights(user, organization, data_source, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user)
    
    payload = {'data_source': data_source.id,
            'id': data_source.id + 'test_organization2',
            'origin_id': 'test_organization2',
            'name': 'test org',
            'parent_organization': f'{url}{organization.id}/'
    }
    
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 201
    assert response.data['parent_organization'] == payload['parent_organization']

@pytest.mark.django_db
def test_post_parent_user_has_no_rights(user2, organization, organization2, data_source, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user2)
    
    payload = {'data_source': data_source.id,
            'id': data_source.id + 'test_organization2',
            'origin_id': 'test_organization2',
            'name': 'test org',
            'parent_organization': f'{url}{organization.id}/'
    }
    
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 403
    assert str(response.data['detail']) == 'User has no rights to this organization'


@pytest.mark.django_db
def test_post_sub_organizations_successfull(user, organization, organization2, data_source, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user)
    
    payload = {'data_source': data_source.id,
            'id': data_source.id + 'test_organization2',
            'origin_id': 'test_organization2',
            'name': 'test org',
            'sub_organizations': [organization.id, organization2.id]
    }
    
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 201
    org_id = response.data['id']
    response = api_client.get(url+org_id+'/', format='json')
    assert set([i.strip('/').split('/')[-1] for i in response.data['sub_organizations']]) == set(payload['sub_organizations'])


@pytest.mark.django_db
def test_post_sub_organizations_wrong_id(user, organization, organization2, data_source, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user)
    
    payload = {'data_source': data_source.id,
            'id': data_source.id + 'test_organization2',
            'origin_id': 'test_organization2',
            'name': 'test org',
            'sub_organizations': ['wrong.id', organization2.id]
    }
    
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 201
    org_id = response.data['id']
    response = api_client.get(url+org_id+'/', format='json')
    assert [i.strip('/').split('/')[-1] for i in response.data['sub_organizations']] == [organization2.id]


@pytest.mark.django_db
def test_post_affiliated_organizations_successfull(user, organization, organization2, data_source, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user)
    
    payload = {'data_source': data_source.id,
            'id': data_source.id + 'test_organization2',
            'origin_id': 'test_organization2',
            'name': 'test org',
            'affiliated_organizations': [f'{url}{organization.id}/', f'{url}{organization2.id}/']
    }
    
    for i in [organization, organization2]:
        i.internal_type = Organization.AFFILIATED
        i.save()

    response = api_client.post(url, payload, format='json')
    assert response.status_code == 201
    org_id = response.data['id']
    response = api_client.get(url+org_id+'/', format='json')
    assert set(response.data['affiliated_organizations']) == set(payload['affiliated_organizations'])


@pytest.mark.django_db
def test_put_user_has_rights(user, organization, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user)

    payload = {'data_source': organization.data_source.id,
            'id': organization.id,
            'name': 'new name',
            'origin_id': 'test_organization',
    }

    response = api_client.put(f'{url}{organization.id}/', payload, format='json')
    assert response.data['name'] == payload['name']



@pytest.mark.django_db
def test_put_user_has_no_rights(user, user2, organization, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user2)

    payload = {'data_source': organization.data_source.id,
            'id': organization.id,
            'name': 'new name',
            'origin_id': 'test_organization',
    }

    response = api_client.put(f'{url}{organization.id}/', payload, format='json')
    assert response.status_code == 403


@pytest.mark.django_db
def test_delete_user_has_rights(user, organization, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user)

    response = api_client.delete(f'{url}{organization.id}/')
    assert response.status_code == 204
    response = api_client.get(f'{url}{organization.id}/', format='json')
    assert response.status_code == 404


@pytest.mark.django_db
def test_delete_user_has_no_rights(user, user2, organization, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user2)

    response = api_client.delete(f'{url}{organization.id}/')
    assert response.status_code == 403


@pytest.mark.django_db
def test_add_users_wrong_field_format(user, user2, organization, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user)

    payload = {'id': organization.id,
                'admin_users': [user.username, user2.username]}

    response = api_client.put(f'{url}{organization.id}/', payload, format='json')
    assert response.data['detail'].code == 'parse_error'


@pytest.mark.django_db
def test_edit_users(user, user2, super_user, organization, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user)
    organization.admin_users.add(super_user)

    payload = {'id': organization.id,
                'admin_users': {'username': [user.username, user2.username]},
                'regular_users': {'username': [user2.username]}}

    response = api_client.put(f'{url}{organization.id}/', payload, format='json')
    assert set(payload['admin_users']['username']) == set([i['username'] for i in response.data['admin_users']])
    assert len(response.data['regular_users']) == 1


@pytest.mark.django_db
def test_user_does_not_remove_itself_from_admins(user, user2, organization, api_client):
    url = reverse('organization-list')
    api_client.force_authenticate(user)

    payload = {'id': organization.id,
                'admin_users': {'username': [user2.username]}}

    response = api_client.put(f'{url}{organization.id}/', payload, format='json')
    assert len(response.data['admin_users']) == 2

