import pytest
from copy import deepcopy
from events.tests.utils import versioned_reverse as reverse
from registrations.models import Registration, SignUp
from events.tests.conftest import *
from events.models import Language


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
def test_filter_events_with_registrations(api_client, user, event, event2):
    registration_url = reverse('registration-list')
    event_url = reverse('event-list')

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}
    response = api_client.post(registration_url, registration_data, format='json')
    assert response.status_code == 201
    
    api_client.force_authenticate(user=None)
    response = api_client.get(event_url, format='json')
    assert response.data['meta']['count'] == 2

    response = api_client.get(f'{event_url}?registration=true', format='json')
    assert response.data['meta']['count'] == 1
    assert response.data['data'][0]['id'] == event.id


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
    l = Language()
    l.id = 'fi'
    l.name = 'finnish'
    l.save()

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}
    response = api_client.post(url, registration_data, format='json')
    registration_id = response.data['id']

    api_client.force_authenticate(user=None)
    sign_up_data = {'registration': registration_id,
                    'name': 'Michael Jackson',
                    'email': 'test@test.com',
                    'phone_number': '0441111111',
                    'notifications': 'sms',
                    'service_language': 'fi',
                    'native_language': 'fi',
                    'street_address': 'my street',
                    'zipcode': 'myzip1'}
    url = reverse('signup-list')

    response = api_client.post(url, sign_up_data, format='json')
    assert response.status_code == 201

    signup = SignUp.objects.first()
    assert signup.name == sign_up_data['name']
    assert signup.email == sign_up_data['email']
    assert signup.phone_number == sign_up_data['phone_number']
    assert signup.notifications == SignUp.NotificationType.SMS
    assert signup.native_language.name == 'finnish'
    assert signup.street_address == sign_up_data['street_address']
    assert signup.zipcode == sign_up_data['zipcode']


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
    registration_data = {"event": event.id,
                         "maximum_attendee_capacity": 10,
                         "waiting_list_capacity": 10}
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


@pytest.mark.django_db
def test_signup_age_is_mandatory_if_audience_min_or_max_age_specified(api_client, user, event):
    registration_url = reverse('registration-list')

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}
    response = api_client.post(registration_url, registration_data, format='json')
    registration_id = response.data['id']

    api_client.force_authenticate(user=None)
    sign_up_data = {'registration': registration_id,
                    'name': 'Michael Jackson',
                    'email': 'test@test.com',
                    'phone_number': '0441111111',
                    'notifications': 'sms'}
    signup_url = reverse('signup-list')

    response = api_client.post(signup_url, sign_up_data, format='json')
    assert response.status_code == 201
    
    api_client.force_authenticate(user=user)
    put_url = f"{registration_url}{registration_id}/"
    registration_data['audience_max_age'] = 100
    response = api_client.put(put_url, registration_data, format='json')
    
    api_client.force_authenticate(user=None)
    sign_up_data2 = {'registration': registration_id,
                    'name': 'Michael Jackson 2',
                    'email': 'test2@test.com',
                    'phone_number': '20441111111',
                    'notifications': 'sms'}
    response = api_client.post(signup_url, sign_up_data2, format='json')
    assert response.status_code == 403
    assert str(response.data['detail']) == 'Date of birth has to be specified.'
    
    sign_up_data2['date_of_birth'] = '1980-12-30'
    response = api_client.post(signup_url, sign_up_data2, format='json')
    assert response.status_code == 201


@pytest.mark.django_db
def test_age_has_to_match_the_audience_min_max_age(api_client, user, event):
    registration_url = reverse('registration-list')

    api_client.force_authenticate(user)
    registration_data = {"event": event.id,
                         "audience_max_age": 40,
                         "audience_min_age": 20}
    response = api_client.post(registration_url, registration_data, format='json')
    registration_id = response.data['id']

    api_client.force_authenticate(user=None)
    sign_up_data = {'registration': registration_id,
                    'name': 'Michael Jackson',
                    'email': 'test@test.com',
                    'phone_number': '0441111111',
                    'notifications': 'sms',
                    'date_of_birth': '2011-04-07'}
    signup_url = reverse('signup-list')

    response = api_client.post(signup_url, sign_up_data, format='json')
    assert response.status_code == 403
    assert str(response.data['detail']) == 'The participant is too young.'


    sign_up_data['date_of_birth'] = '1879-03-14'
    response = api_client.post(signup_url, sign_up_data, format='json')
    assert response.status_code == 403
    assert str(response.data['detail']) == 'The participant is too old.'

    sign_up_data['date_of_birth'] = '2000-02-29'
    response = api_client.post(signup_url, sign_up_data, format='json')
    assert response.status_code == 201


@pytest.mark.django_db
def test_signup_deletion(api_client, user, event):
    registration_url = reverse('registration-list')

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}

    response = api_client.post(registration_url, registration_data, format='json')
    registration_id = response.data['id']

    api_client.force_authenticate(user=None)
    sign_up_payload = {'registration': registration_id,
                    'name': 'Michael Jackson',
                    'email': 'test@test.com',
                    'phone_number': '0441111111',
                    'notifications': 'sms',
                    'date_of_birth': '2011-04-07'}
    signup_url = reverse('signup-list')

    response = api_client.post(signup_url, sign_up_payload, format='json')
    delete_payload = {'cancellation_code': response.data['cancellation_code']}
     
    response = api_client.delete(signup_url, delete_payload, format='json')
    assert response.status_code == 200


@pytest.mark.django_db
def test_signup_deletion_missing_signup(api_client, user, event):
    registration_url = reverse('registration-list')

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}

    response = api_client.post(registration_url, registration_data, format='json')
    registration_id = response.data['id']

    api_client.force_authenticate(user=None)
    sign_up_payload = {'registration': registration_id,
                    'name': 'Michael Jackson',
                    'email': 'test@test.com',
                    'phone_number': '0441111111',
                    'notifications': 'sms',
                    'date_of_birth': '2011-04-07'}
    signup_url = reverse('signup-list')

    response = api_client.post(signup_url, sign_up_payload, format='json')
    delete_payload = {'cancellation_code': response.data['cancellation_code']}
     
    response = api_client.delete(signup_url, delete_payload, format='json')
    response = api_client.delete(signup_url, delete_payload, format='json')
    assert response.status_code == 403


@pytest.mark.django_db
def test_signup_deletion_wrong_code(api_client, user, event):
    registration_url = reverse('registration-list')

    api_client.force_authenticate(user)
    registration_data = {"event": event.id}

    response = api_client.post(registration_url, registration_data, format='json')
    registration_id = response.data['id']

    api_client.force_authenticate(user=None)
    sign_up_payload = {'registration': registration_id,
                    'name': 'Michael Jackson',
                    'email': 'test@test.com',
                    'phone_number': '0441111111',
                    'notifications': 'sms',
                    'date_of_birth': '2011-04-07'}
    signup_url = reverse('signup-list')

    response = api_client.post(signup_url, sign_up_payload, format='json')
    delete_payload = {'cancellation_code': 'not a code'}
     
    response = api_client.delete(signup_url, delete_payload, format='json')
    assert str(response.data['detail']) == 'Malformed UUID.'
    assert response.status_code == 403


@pytest.mark.django_db
def test_signup_deletion_leads_to_changing_status_of_first_waitlisted_user(api_client, user, event):
    registration_url = reverse('registration-list')

    api_client.force_authenticate(user)
    registration_data = {"event": event.id,
                         "maximum_attendee_capacity": 1}

    response = api_client.post(registration_url, registration_data, format='json')
    registration_id = response.data['id']

    api_client.force_authenticate(user=None)
    sign_up_payload = {'registration': registration_id,
                       'name': 'Michael Jackson1',
                       'email': 'test@test.com'}
    signup_url = reverse('signup-list')

    response = api_client.post(signup_url, sign_up_payload, format='json')
    delete_payload = {'cancellation_code': response.data['cancellation_code']}

    sign_up_payload2 = {'registration': registration_id,
                        'name': 'Michael Jackson2',
                        'email': 'test1@test.com'}
    api_client.post(signup_url, sign_up_payload2, format='json')

    sign_up_payload3 = {'registration': registration_id,
                        'name': 'Michael Jackson3',
                        'email': 'test2@test.com'}
    api_client.post(signup_url, sign_up_payload3, format='json')
    
    assert SignUp.objects.get(email='test2@test.com').attendee_status == SignUp.AttendeeStatus.WAITING_LIST
    assert SignUp.objects.get(email='test1@test.com').attendee_status == SignUp.AttendeeStatus.WAITING_LIST
    assert SignUp.objects.get(email='test@test.com').attendee_status == SignUp.AttendeeStatus.ATTENDING


    response = api_client.delete(signup_url, delete_payload, format='json')
    assert SignUp.objects.get(email='test1@test.com').attendee_status == SignUp.AttendeeStatus.ATTENDING
    assert SignUp.objects.get(email='test2@test.com').attendee_status == SignUp.AttendeeStatus.WAITING_LIST
