import pytest
from copy import deepcopy
from events.tests.utils import versioned_reverse as reverse
from registrations.models import Registration, SignUp
from events.tests.conftest import *


@pytest.mark.django_db
def test_basic_registration_functionality(api_client, user, user2, event):
    url = reverse('registration-list')

    # create registration, user has no rights to modify event
    api_client.force_authenticate(user2)
    registration_data = {"event": event.id}
    response = api_client.post(url, registration_data, format='json')
    assert response.status_code == 403

    # create registration, user has rights
    api_client.force_authenticate(user)
    registration_data = {"event": event.id}
    response = api_client.post(url, registration_data, format='json')
    assert response.status_code == 201

    # modify registration
    assert response.data['audience_max_age'] is None
    registration_data['audience_max_age'] = 10
    put_url = f"{url}{response.data['id']}/"
    response = api_client.put(put_url, registration_data, format='json')
    assert response.status_code == 200
    assert response.data['audience_max_age'] == 10

    # user from another organization cannot modify registration
    api_client.force_authenticate(user2)
    response = api_client.put(put_url, registration_data, format='json')
    assert response.status_code == 403

    # only one registration per event
    api_client.force_authenticate(user)
    response = api_client.post(url, registration_data, format='json')
    assert response.status_code == 400

    # user with appropriate rights can delete registration
    api_client.force_authenticate(user)
    response = api_client.delete(put_url)
    assert response.status_code == 204
    assert len(Registration.objects.all()) == 0

    # no registration for a nonexistent event
    registration_data = {"event": "nonexistent-id"}
    response = api_client.post(url, registration_data, format='json')
    assert response.status_code == 403


@pytest.mark.django_db
def test_successful_sign_up(api_client, user, event):
    url = reverse('registration-list')

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}
    response = api_client.post(url, registration_data, format='json')
    registration_id = response.data['id']

    api_client.force_authenticate(user=None)
    sign_up_data = {'registration': registration_id,
                    'name': 'Michael Jackson',
                    'email': 'test@test.com',
                    'phone_number': '0441111111'}
    url = reverse('signup-list')

    response = api_client.post(url, sign_up_data, format='json')
    assert response.status_code == 201

    signup = SignUp.objects.first()
    assert signup.name == sign_up_data['name']
    assert signup.email == sign_up_data['email']
    assert signup.phone_number == sign_up_data['phone_number']


@pytest.mark.django_db
def test_wrong_registration_id(api_client):
    url = reverse('signup-list')

    sign_up_data = {'registration': 1,
                    'name': 'Michael Jackson',
                    'email': 'test@test.com',
                    'phone_number': '0441111111'}
    response = api_client.post(url, sign_up_data, format='json')
    assert response.status_code == 400


@pytest.mark.django_db
def test_cannot_sign_up_twice_with_same_phone_or_email(api_client, user, event):
    url = reverse('registration-list')

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}
    response = api_client.post(url, registration_data, format='json')
    registration_id = response.data['id']

    api_client.force_authenticate(user=None)
    sign_up_data = {'registration': registration_id,
                    'name': 'Michael Jackson',
                    'email': 'test@test.com',
                    'phone_number': '0441111111'}
    url = reverse('signup-list')
    response = api_client.post(url, sign_up_data, format='json')
    assert response.status_code == 201

    # cannot signup with the same email twice
    sign_up_data_same_email = deepcopy(sign_up_data)
    sign_up_data_same_email['phone_number'] = '0442222222'
    response = api_client.post(url, sign_up_data_same_email, format='json')
    print(response.data)
    assert response.status_code == 400

    # cannot signup with the same phone twice
    sign_up_data_same_phone = deepcopy(sign_up_data)
    sign_up_data_same_phone['email'] = 'another@email.com'
    response = api_client.post(url, sign_up_data_same_email, format='json')
    assert response.status_code == 400
