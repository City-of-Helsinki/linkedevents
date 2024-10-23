from datetime import timedelta

from django.core.management import BaseCommand
from django.utils.timezone import localtime

from registrations.models import SignUpPayment


class Command(BaseCommand):
    help = (
        "Delete signups and signup groups that have payments that have expired at least the given "  # noqa: E501
        "amount of days ago. The payments will be deleted along with the signups."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold_days",
            type=int,
            default=14,
            help="How many days ago the payments should have expired before they are deleted."  # noqa: E501
            "Default = 14.",
        )

    def handle(self, *args, **options):
        threshold_datetime = localtime() - timedelta(days=options["threshold_days"])

        for payment in SignUpPayment.all_objects.select_related(
            "signup", "signup_group"
        ).filter(
            status=SignUpPayment.PaymentStatus.EXPIRED,
            expires_at__lte=threshold_datetime,
        ):
            if signup_group := getattr(payment, "signup_group", None):
                signup_group.delete()
            elif signup := getattr(payment, "signup", None):
                signup._individually_deleted = True
                signup.delete()
