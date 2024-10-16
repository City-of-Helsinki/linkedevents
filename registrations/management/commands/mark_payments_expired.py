import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction
from django.utils.timezone import localtime
from requests import RequestException
from rest_framework import status

from registrations.models import SignUp, SignUpPayment
from registrations.notifications import SignUpNotificationType
from registrations.utils import (
    get_access_code_for_contact_person,
    move_waitlisted_to_attending,
)
from web_store.order.clients import WebStoreOrderAPIClient
from web_store.payment.clients import WebStorePaymentAPIClient
from web_store.payment.enums import WebStorePaymentStatus

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Mark signup payments expired if their expires_at timestamp has been exceeded and no "  # noqa: E501
        "payment exists in the Talpa web store for them."
    )

    @staticmethod
    def _handle_payment_paid(payment):
        payment.status = SignUpPayment.PaymentStatus.PAID
        payment.save(update_fields=["status"])

        contact_person = payment.signup_or_signup_group.actual_contact_person
        if not contact_person:
            return

        access_code = get_access_code_for_contact_person(
            contact_person, payment.signup_or_signup_group.created_by
        )
        contact_person.send_notification(
            SignUpNotificationType.CONFIRMATION, access_code=access_code
        )

    @staticmethod
    def _handle_payment_cancelled(payment):
        if isinstance(payment.signup_or_signup_group, SignUp):
            payment.signup_or_signup_group._individually_deleted = True

        payment.signup_or_signup_group.delete(
            bypass_web_store_api_calls=True, payment_cancelled=True
        )

    @staticmethod
    def _handle_payment_expired(payment, order_api_client):
        payment.status = SignUpPayment.PaymentStatus.EXPIRED
        payment.save(update_fields=["status"])

        user = getattr(payment, "created_by", None)

        try:
            # Talpa recommends to cancel the order in this case.
            order_api_client.cancel_order(
                payment.external_order_id, user_uuid=str(getattr(user, "uuid", ""))
            )
        except RequestException as exc:
            status_code = getattr(exc.response, "status_code", None)

            logger.error(
                f"mark_payments_expired: an error occurred while cancelling order "
                f"in the Talpa API (payment ID: {payment.pk}, order ID: "
                f"{payment.external_order_id}, response.status_code: {status_code})"
            )

        signup_or_signup_group = payment.signup_or_signup_group

        if getattr(signup_or_signup_group, "is_attending", None) or getattr(
            signup_or_signup_group, "attending_signups", None
        ):
            move_waitlisted_to_attending(signup_or_signup_group.registration, count=1)

        contact_person = signup_or_signup_group.actual_contact_person
        if contact_person:
            contact_person.send_notification(SignUpNotificationType.PAYMENT_EXPIRED)

        signup_or_signup_group.soft_delete()

    def handle(self, *args, **options):
        payment_api_client = WebStorePaymentAPIClient()
        order_api_client = WebStoreOrderAPIClient()
        datetime_now = localtime()
        local_tz = ZoneInfo(settings.TIME_ZONE)
        utc_tz = ZoneInfo("UTC")

        expired_payments = SignUpPayment.objects.select_for_update().filter(
            status=SignUpPayment.PaymentStatus.CREATED,
            expires_at__lt=datetime_now,
        )

        with transaction.atomic():
            for payment in expired_payments:
                try:
                    resp_json = payment_api_client.get_payment(
                        payment.external_order_id
                    )
                except RequestException as exc:
                    status_code = getattr(exc.response, "status_code", None)

                    if status_code and status_code == status.HTTP_404_NOT_FOUND:
                        # No payment found from Talpa => continue payment expiry
                        # processing.
                        resp_json = {}
                    else:
                        # Request failed => log error and skip processing for this
                        # payment.
                        logger.error(
                            f"mark_payments_expired: an error occurred while fetching payment "  # noqa: E501
                            f"from the Talpa API (payment ID: {payment.pk}, order ID: "
                            f"{payment.external_order_id}, response.status_code: {status_code})"  # noqa: E501
                        )
                        continue

                if resp_json.get("status") == WebStorePaymentStatus.PAID.value:
                    # Payment exists and is paid => mark our payment as paid and notify contact  # noqa: E501
                    # person.
                    self._handle_payment_paid(payment)
                elif resp_json.get("status") == WebStorePaymentStatus.CANCELLED.value:
                    # Payment exists and is cancelled => delete our payment and related
                    # signup.
                    self._handle_payment_cancelled(payment)
                elif (
                    resp_json.get("status") == WebStorePaymentStatus.CREATED.value
                    and resp_json.get("timestamp")
                    and (
                        datetime.strptime(resp_json["timestamp"], "%Y%m%d-%H%M%S")
                        .replace(tzinfo=utc_tz)
                        .astimezone(local_tz)
                    )
                    > payment.expires_at
                ):
                    # Payer has entered the payment phase after expiry datetime and might make a  # noqa: E501
                    # payment => check again later.
                    pass
                else:
                    # Payment is expired => Mark our payment as expired and notify
                    # contact person.
                    self._handle_payment_expired(payment, order_api_client)
