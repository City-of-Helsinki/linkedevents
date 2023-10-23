from datetime import timedelta

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction
from django.utils.timezone import localtime

from registrations.models import SignUp, SignUpGroup


class Command(BaseCommand):
    help = (
        "Pseudonymize signups and signup groups for past events. "
        "The time of pseudonymization can be specified in days in the "
        "PSEUDONYMIZATION_THRESHOLD_DAYS environment variable."
    )

    def handle(self, *args, **options):
        threshold_time = localtime() - timedelta(
            days=settings.PSEUDONYMIZATION_THRESHOLD_DAYS
        )

        # Pseudonymize all the signup groups and the related signups
        self.stdout.write(
            "Start pseudonymizing past signup groups and the related signups"
        )
        signup_groups = (
            SignUpGroup.objects.prefetch_related("signups")
            .select_for_update()
            .filter(
                registration__event__end_time__lt=threshold_time,
                pseudonymization_time__isnull=True,
            )
        )

        with transaction.atomic():
            for signup_group in signup_groups:
                signup_group.pseudonymize()
        self.stdout.write(f"{len(signup_groups)} signup groups updated")

        # Pseudonymize all signups without a group
        self.stdout.write("Start pseudonymizing past signups")
        signups = SignUp.objects.select_for_update().filter(
            registration__event__end_time__lt=threshold_time,
            pseudonymization_time__isnull=True,
        )

        with transaction.atomic():
            for signup in signups:
                signup.pseudonymize()
        self.stdout.write(f"{len(signups)} signups updated")
