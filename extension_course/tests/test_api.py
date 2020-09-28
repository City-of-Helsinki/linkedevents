from copy import deepcopy
from datetime import timedelta

import pytest
from django.utils import dateparse, timezone

from events.models import Event
from events.tests.test_event_get import get_detail, get_list
from events.tests.utils import assert_fields_exist, post_event, put_event
from extension_course.models import Course

COURSE_DATA = {
    'enrolment_start_time': "2118-06-11T07:11:05.184117Z",
    'enrolment_end_time': "2118-06-12T07:11:05.184117Z",
    'maximum_attendee_capacity': 200,
    'minimum_attendee_capacity': 20,
    'remaining_attendee_capacity': 100,
}


COURSE_FIELDS = set(COURSE_DATA.keys())


@pytest.fixture
def minimal_event_with_course_dict(minimal_event_dict):
    data = deepcopy(minimal_event_dict)
    data['extension_course'] = COURSE_DATA
    return data


@pytest.fixture
def event_with_course(event):
    Course.objects.get_or_create(event=event, defaults={
        'enrolment_start_time': timezone.now() - timedelta(days=1),
        'enrolment_end_time': timezone.now() + timedelta(days=1),
        'maximum_attendee_capacity': 100,
        'minimum_attendee_capacity': 10,
        'remaining_attendee_capacity': 50,
    })
    return event


def check_extension_data(data, course):
    assert_fields_exist(data, COURSE_FIELDS)
    assert dateparse.parse_datetime(data['enrolment_start_time']) == course.enrolment_start_time
    assert dateparse.parse_datetime(data['enrolment_end_time']) == course.enrolment_end_time
    assert data['maximum_attendee_capacity'] == course.maximum_attendee_capacity
    assert data['minimum_attendee_capacity'] == course.minimum_attendee_capacity
    assert data['remaining_attendee_capacity'] == course.remaining_attendee_capacity


@pytest.mark.django_db
def test_get_course_list(user_api_client, event_with_course):
    response = get_list(user_api_client)
    extension_data = response.data['data'][0]['extension_course']
    check_extension_data(extension_data, event_with_course.extension_course)


@pytest.mark.django_db
def test_get_course_detail(user_api_client, event_with_course):
    response = get_detail(user_api_client, event_with_course.pk)
    extension_data = response.data['extension_course']
    check_extension_data(extension_data, event_with_course.extension_course)


@pytest.mark.django_db
def test_post_course(minimal_event_with_course_dict, user_api_client):
    response = post_event(user_api_client, minimal_event_with_course_dict)
    assert Course.objects.count() == 1

    event = Event.objects.latest('id')
    course = Course.objects.get(event=event)
    check_extension_data(response.data['extension_course'], course)
    check_extension_data(COURSE_DATA, course)


@pytest.mark.django_db
def test_put_course(event_with_course, minimal_event_with_course_dict, user_api_client):
    response = put_event(user_api_client, event_with_course, minimal_event_with_course_dict)
    assert Course.objects.count() == 1

    course = event_with_course.extension_course
    course.refresh_from_db()
    check_extension_data(response.data['extension_course'], course)
    check_extension_data(COURSE_DATA, course)
