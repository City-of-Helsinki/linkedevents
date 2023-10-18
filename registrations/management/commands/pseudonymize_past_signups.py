from datetime import timedelta

from django.conf import settings
from django.core.management import BaseCommand
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
        signup_groups = SignUpGroup.objects.filter(
            registration__event__end_time__lt=threshold_time,
            pseudonymization_time__isnull=True,
        )

        # Pseudonymize all the signup groups and the signups they have
        self.stdout.write(
            f"Start pseudonymizing past signup groups ({len(signup_groups)}) and the signups they have"
        )
        for signup_group in signup_groups:
            signup_group.pseudonymize()
        self.stdout.write("Signup groups updated")

        signups = SignUp.objects.filter(
            registration__event__end_time__lt=threshold_time,
            pseudonymization_time__isnull=True,
        )

        # Pseudonymize all signups without a group
        self.stdout.write(f"Start pseudonymizing past signups ({len(signups)})")
        for signup in signups:
            signup.pseudonymize()
        self.stdout.write("Signups updated")
