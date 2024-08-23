from decimal import Decimal
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied

from helevents.tests.factories import UserFactory
from registrations.enums import VatPercentage
from registrations.models import SignUp, SignUpContactPerson, SignUpPriceGroup
from registrations.serializers import SignUpSerializer
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationPriceGroupFactory,
)


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
        "contact_person": {
            "first_name": "Contact",
            "last_name": "Person",
            "email": "contact@test.com",
        },
    }

    request_mock = Mock(user=UserFactory())

    serializer = SignUpSerializer(
        data=signup_payload, context={"request": request_mock}
    )
    serializer.is_valid(raise_exception=True)

    assert SignUp.objects.count() == 0
    assert SignUpContactPerson.objects.count() == 0

    if expected_signups_count == 0:
        with pytest.raises(DRFPermissionDenied):
            serializer.create(serializer.validated_data)
    else:
        serializer.create(serializer.validated_data)

    assert SignUp.objects.count() == expected_signups_count
    assert SignUpContactPerson.objects.count() == expected_signups_count
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


@pytest.mark.django_db
def test_signup_create_with_price_group(registration):
    registration_price_group = RegistrationPriceGroupFactory(
        registration=registration,
        price_group__publisher=registration.publisher,
        price=Decimal("100"),
        vat_percentage=VatPercentage.VAT_24.value,
    )

    signup_payload = {
        "registration": registration.pk,
        "first_name": "User",
        "last_name": "1",
        "email": "test1@test.com",
        "price_group": {
            "registration_price_group": registration_price_group.pk,
        },
    }

    request_mock = Mock(user=UserFactory())

    serializer = SignUpSerializer(
        data=signup_payload, context={"request": request_mock}
    )
    serializer.is_valid(raise_exception=True)

    assert SignUp.objects.count() == 0
    assert SignUpPriceGroup.objects.count() == 0

    serializer.create(serializer.validated_data)

    assert SignUp.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1

    signup_price_group = SignUpPriceGroup.objects.first()
    assert signup_price_group.signup_id == SignUp.objects.first().pk
    assert (
        signup_price_group.description
        == registration_price_group.price_group.description
    )
    assert signup_price_group.price == registration_price_group.price
    assert signup_price_group.vat_percentage == registration_price_group.vat_percentage
    assert (
        signup_price_group.price_without_vat
        == registration_price_group.price_without_vat
    )
    assert signup_price_group.vat == registration_price_group.vat
