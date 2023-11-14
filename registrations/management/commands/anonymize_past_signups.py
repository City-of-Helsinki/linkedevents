from datetime import timedelta

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction
from django.utils.timezone import localtime

from registrations.models import SignUp, SignUpGroup


class Command(BaseCommand):
    help = (
        "Anonymize signups and signup groups of the registration with past "
        "enrolment times. The threshold of anonymization can be specified as "
        "days in the ANONYMIZATION_THRESHOLD_DAYS environment variable."
    )

    def handle(self, *args, **options):
        threshold_time = localtime() - timedelta(
            days=settings.ANONYMIZATION_THRESHOLD_DAYS
        )

        # Anonymize all the signup groups and the related signups
        self.stdout.write(
            "Start anonymizing past signup groups and the related signups"
        )
        signup_groups = (
            SignUpGroup.objects.prefetch_related("signups")
            .select_for_update()
            .filter(
                registration__event__end_time__lt=threshold_time,
                anonymization_time__isnull=True,
            )
        )

        with transaction.atomic():
            for signup_group in signup_groups:
                signup_group.anonymize()
        self.stdout.write(f"{len(signup_groups)} signup groups anonymized")

        # Anonymize all signups without a group
        self.stdout.write("Start anonymizing past signups")
        signups = SignUp.objects.select_for_update().filter(
            registration__event__end_time__lt=threshold_time,
            anonymization_time__isnull=True,
        )

        with transaction.atomic():
            for signup in signups:
                signup.anonymize()
        self.stdout.write(f"{len(signups)} signups anonymized")
