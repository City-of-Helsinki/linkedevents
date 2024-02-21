from datetime import timedelta

import freezegun
import pytest
from django.core.management import call_command
from django.utils.timezone import localtime

from registrations.models import SignUp, SignUpGroup, SignUpPayment
from registrations.tests.factories import SignUpGroupFactory, SignUpPaymentFactory


@pytest.mark.parametrize(
    "threshold_days,expected_remaining_signups_count,expected_remaining_groups_count",
    [
        ("default", 5, 0),
        (7, 3, 0),
        (30, 6, 1),
    ],
)
@freezegun.freeze_time("2024-02-16 16:45:00+02:00")
@pytest.mark.django_db
def test_delete_signups_with_expired_payments(
    threshold_days, expected_remaining_signups_count, expected_remaining_groups_count
):
    now = localtime()
    thirty_days_ago = now - timedelta(days=30)
    two_weeks_ago = now - timedelta(days=14)
    thirteen_days_ago = now - timedelta(days=13)
    one_week_ago = now - timedelta(days=7)

    # Should be deleted.
    SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.EXPIRED,
        expires_at=thirty_days_ago,
        deleted=True,
    )
    SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.EXPIRED,
        expires_at=two_weeks_ago,
        deleted=True,
    )
    SignUpPaymentFactory(
        signup=None,
        signup_group=SignUpGroupFactory(),
        status=SignUpPayment.PaymentStatus.EXPIRED,
        expires_at=two_weeks_ago,
        deleted=True,
    )

    SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.EXPIRED,
        expires_at=thirteen_days_ago,
        deleted=True,
    )
    SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.EXPIRED,
        expires_at=one_week_ago,
        deleted=True,
    )
    SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.CREATED, expires_at=two_weeks_ago
    )
    SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.PAID, expires_at=two_weeks_ago
    )
    SignUpPaymentFactory(
        status=SignUpPayment.PaymentStatus.CANCELLED, expires_at=two_weeks_ago
    )

    remaining_payments_count = (
        expected_remaining_signups_count + expected_remaining_groups_count
    )
    threshold_datetime = localtime() - timedelta(
        days=14 if threshold_days == "default" else threshold_days
    )

    assert SignUp.all_objects.count() == 7
    assert SignUpGroup.all_objects.count() == 1
    assert SignUpPayment.all_objects.count() == 8
    assert (
        SignUpPayment.all_objects.filter(
            status=SignUpPayment.PaymentStatus.EXPIRED,
            expires_at__lte=threshold_datetime,
        ).count()
        == 8 - remaining_payments_count
    )

    if threshold_days == "default":
        call_command("delete_signups_with_expired_payments")
    else:
        call_command(
            "delete_signups_with_expired_payments", threshold_days=threshold_days
        )

    assert SignUp.all_objects.count() == expected_remaining_signups_count
    assert SignUpGroup.all_objects.count() == expected_remaining_groups_count
    assert SignUpPayment.all_objects.count() == remaining_payments_count
    assert (
        SignUpPayment.all_objects.filter(
            status=SignUpPayment.PaymentStatus.EXPIRED,
            expires_at__lte=threshold_datetime,
        ).count()
        == 0
    )
