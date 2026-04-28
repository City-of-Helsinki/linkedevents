from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import DateTimeField, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from helevents.models import User
from registrations.models import SignUp


class Command(BaseCommand):
    help = "Delete users that have been inactive for a configurable number of years."

    @staticmethod
    def _has_active_signups(user_ids):
        """Return user IDs that have active (non-cancelled) signups."""
        active_statuses = (
            SignUp.AttendeeStatus.ATTENDING,
            SignUp.AttendeeStatus.AWAITING_PAYMENT,
            SignUp.AttendeeStatus.WAITING_LIST,
        )
        return set(
            User.objects.filter(pk__in=user_ids)
            .filter(
                Q(contact_persons__signup__attendee_status__in=active_statuses)
                | Q(
                    contact_persons__signup_group__signups__attendee_status__in=active_statuses
                )
                | Q(signup_created_by__attendee_status__in=active_statuses)
            )
            .values_list("pk", flat=True)
        )

    def handle(self, *args, **options):
        now = timezone.now()

        threshold_time = now - relativedelta(
            years=settings.INACTIVE_USER_DELETION_YEARS
        )

        # For users without a last_api_use timestamp, fall back to date_joined.
        candidates = (
            User.objects.annotate(
                last_activity=Coalesce(
                    "last_api_use", "date_joined", output_field=DateTimeField()
                )
            )
            .filter(last_activity__lt=threshold_time)
            .values_list("pk", flat=True)
        )
        candidate_ids = list(candidates)

        skipped_ids = self._has_active_signups(candidate_ids)
        deletable_ids = [pk for pk in candidate_ids if pk not in skipped_ids]

        deleted_count, _ = User.objects.filter(pk__in=deletable_ids).delete()
        skipped_count = len(skipped_ids)

        self.stdout.write(
            self.style.SUCCESS(
                f"{deleted_count} inactive user(s) deleted, "
                f"{skipped_count} skipped due to active signups."
            )
        )
