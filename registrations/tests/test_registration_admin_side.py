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
def test_list_all_registrations(api_client, user, user2, event, event2, event3):
    url = reverse('registration-list')

    # create registrations from two different users
    api_client.force_authenticate(user)
    registration_data = {"event": event.id}
    response = api_client.post(url, registration_data, format='json')
    assert response.status_code == 201
    registration_data = {"event": event3.id}
    response = api_client.post(url, registration_data, format='json')
    assert response.status_code == 201

    api_client.force_authenticate(user2)
    registration_data = {"event": event2.id}
    response = api_client.post(url, registration_data, format='json')
    assert response.status_code == 201

    # log out and check the list of registrations
    api_client.force_authenticate(user=None)
    response = api_client.get(url)
    assert response.status_code == 200
    


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
                    'phone_number': '0441111111',
                    'notifications': 'sms'}
    url = reverse('signup-list')

    response = api_client.post(url, sign_up_data, format='json')
    assert response.status_code == 201

    signup = SignUp.objects.first()
    assert signup.name == sign_up_data['name']
    assert signup.email == sign_up_data['email']
    assert signup.phone_number == sign_up_data['phone_number']
    assert signup.notifications == SignUp.NotificationType.SMS


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

@pytest.mark.django_db
def test_current_attendee_and_waitlist_count(api_client, user, event):
    url = reverse('registration-list')

    api_client.force_authenticate(user)
    registration_data = {"event": event.id,
                         "maximum_attendee_capacity": 1,
                         "waiting_list_capacity": 1}
    response = api_client.post(url, registration_data, format='json')
    registration_id = response.data['id']

    api_client.force_authenticate(user=None)
    sign_up_data = {'registration': registration_id,
                    'name': 'Michael Jackson',
                    'email': 'test@test.com',
                    'phone_number': '0441111111',
                    'notifications': 'sms'}
    signup_url = reverse('signup-list')
    registration_detail_url = f'{url}{registration_id}/'

    response = api_client.get(registration_detail_url, format='json')
    assert response.data['current_attendee_count'] == 0
    assert response.data['current_waiting_list_count'] == 0

    api_client.post(signup_url, sign_up_data, format='json')
    response = api_client.get(registration_detail_url, format='json')
    assert response.data['current_attendee_count'] == 1
    assert response.data['current_waiting_list_count'] == 0

    sign_up_data2 = {'registration': registration_id,
                    'name': 'Michael Jackson 2',
                    'email': 'test2@test.com',
                    'phone_number': '20441111111',
                    'notifications': 'sms'}
    api_client.post(signup_url, sign_up_data2, format='json')
    response = api_client.get(registration_detail_url, format='json')
    assert response.data['current_attendee_count'] == 1
    assert response.data['current_waiting_list_count'] == 1

    sign_up_data3 = {'registration': registration_id,
                    'name': 'Michael Jackson 3',
                    'email': 'test3@test.com',
                    'phone_number': '30441111111',
                    'notifications': 'sms'}
    api_client.post(signup_url, sign_up_data3, format='json')
    response = api_client.get(registration_detail_url, format='json')
    assert response.data['current_attendee_count'] == 1
    assert response.data['current_waiting_list_count'] == 1
