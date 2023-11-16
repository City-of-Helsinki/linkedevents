from unittest.mock import Mock

import pytest
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied

from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.serializers import SignUpSerializer
from registrations.tests.factories import RegistrationFactory


@pytest.mark.no_test_audit_log
@pytest.mark.parametrize(
    "maximum_attendee_capacity,waiting_list_capacity,expected_signups_count,"
    "expected_attending,expected_waitlisted",
    [
        (0, 0, 0, 0, 0),
        (1, 1, 1, 1, 0),
        (1, 0, 1, 1, 0),
        (0, 1, 1, 0, 1),
        (2, 1, 1, 1, 0),
        (0, 2, 1, 0, 1),
        (None, None, 1, 1, 0),
        (None, 1, 1, 1, 0),
        (1, None, 1, 1, 0),
        (0, None, 1, 0, 1),
    ],
)
@pytest.mark.django_db
def test_signup_create(
    maximum_attendee_capacity,
    waiting_list_capacity,
    expected_signups_count,
    expected_attending,
    expected_waitlisted,
):
    registration = RegistrationFactory(
        maximum_attendee_capacity=maximum_attendee_capacity,
        waiting_list_capacity=waiting_list_capacity,
    )

    signup_payload = {
        "registration": registration.pk,
        "first_name": "User",
        "last_name": "1",
        "email": "test1@test.com",
    }

    request_mock = Mock(user=UserFactory())

    serializer = SignUpSerializer(
        data=signup_payload, context={"request": request_mock}
    )
    serializer.is_valid(raise_exception=True)

    assert SignUp.objects.count() == 0

    if expected_signups_count == 0:
        with pytest.raises(DRFPermissionDenied):
            serializer.create(serializer.validated_data)
    else:
        serializer.create(serializer.validated_data)

    assert SignUp.objects.count() == expected_signups_count
    assert (
        SignUp.objects.filter(attendee_status=SignUp.AttendeeStatus.ATTENDING).count()
        == expected_attending
    )
    assert (
        SignUp.objects.filter(
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST
        ).count()
        == expected_waitlisted
    )
