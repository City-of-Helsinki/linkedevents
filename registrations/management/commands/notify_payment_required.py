import logging
from datetime import timedelta

from django.conf import settings
from django.core.management import BaseCommand
from django.utils import timezone

from registrations.models import SignUpPayment
from registrations.notifications import SignUpNotificationType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Notify user that the payment is required for the signup to be valid."

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold_minutes",
            type=int,
            default=settings.PAYMENT_REQUIRED_NOTIFY_THRESHOLD_MINUTES,
            help="How many minutes after the payment creation, if not paid, "
            "the notification should be sent.",
        )

    def handle(self, *args, **options):
        if not settings.WEB_STORE_INTEGRATION_ENABLED:
            logger.info(
                "Web store integration is disabled, skipping payment notifications"
            )
            return

        notify_payments = SignUpPayment.objects.filter(
            status=SignUpPayment.PaymentStatus.CREATED,
            expiry_notification_sent_at__isnull=True,
            checkout_url__isnull=False,
            created_time__lte=timezone.now()
            - timedelta(minutes=options["threshold_minutes"]),
        )

        for payment in notify_payments:
            contact_person = payment.signup.actual_contact_person
            if not contact_person:
                logger.error("Contact person not found for payment %s", payment.id)

            try:
                contact_person.send_notification(
                    SignUpNotificationType.CONFIRMATION_WITH_PAYMENT,
                    payment_link=payment.checkout_url,
                    payment_expiry_time=payment.expires_at,
                )
            except Exception as e:
                logger.exception(
                    f"An unexpected error occurred while sending signup payment "
                    f"notification: {str(e)}"
                )
            else:
                logger.info(
                    f"Notification sent for payment {payment.id}  related to signup "
                    f"{payment.signup_id})"
                )
                payment.expiry_notification_sent_at = timezone.now()
                payment.save(update_fields=["expiry_notification_sent_at"])
