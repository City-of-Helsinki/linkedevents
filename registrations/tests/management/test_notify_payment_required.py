import pytest
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from registrations.models import SignUpContactPerson, SignUpPayment
from registrations.tests.factories import (
    SignUpPaymentFactory,
)
from registrations.tests.utils import assert_payment_link_email_sent


@pytest.mark.django_db
def test_payment_link_is_sent_to_contact_person(signup):
    creation_time = timezone.now()
    with freeze_time(creation_time):
        payment = SignUpPaymentFactory(
            signup=signup,
            checkout_url="https://check.out",
            expires_at=creation_time + timezone.timedelta(days=2),
        )

    notification_time = creation_time + timezone.timedelta(minutes=60)
    with freeze_time(notification_time):
        call_command("notify_payment_required")

    payment.refresh_from_db()
    assert payment.expiry_notification_sent_at is not None

    assert_payment_link_email_sent(
        SignUpContactPerson.objects.first(),
        SignUpPayment.objects.first(),
        expected_subject="Maksu vaaditaan ilmoittautumisen vahvistamiseksi - tapahtuma",
        expected_text="Voit vahvistaa ilmoittautumisesi tapahtumaan "
        "<strong>tapahtuma</strong> oheisen maksulinkin avulla. Maksulinkki vanhenee "
        "%(exp_date)s."
        % {
            "exp_date": timezone.localtime(payment.expires_at).strftime(
                "%d.%m.%Y %H:%M"
            )
        },
    )


@pytest.mark.django_db
@override_settings(PAYMENT_REQUIRED_NOTIFY_THRESHOLD_MINUTES=120)
def test_notify_payment_required_respects_threshold_setting(signup):
    creation_time = timezone.now()
    with freeze_time(creation_time):
        payment = SignUpPaymentFactory(signup=signup, checkout_url="https://check.out")

    notification_time = creation_time + timezone.timedelta(minutes=60)
    with freeze_time(notification_time):
        call_command("notify_payment_required")

    payment.refresh_from_db()
    assert payment.expiry_notification_sent_at is None

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_notify_payment_does_not_send_notification_if_already_sent(signup, signup2):
    creation_time = timezone.now()
    with freeze_time(creation_time):
        SignUpPaymentFactory(
            signup=signup,
            checkout_url="https://check.out",
            expiry_notification_sent_at=timezone.now(),
            expires_at=creation_time + timezone.timedelta(days=2),
        )
        SignUpPaymentFactory(
            signup=signup2,
            checkout_url="https://check.out",
            expires_at=creation_time + timezone.timedelta(days=2),
        )

    notification_time = creation_time + timezone.timedelta(minutes=60)
    with freeze_time(notification_time):
        call_command("notify_payment_required")

    assert len(mail.outbox) == 1
