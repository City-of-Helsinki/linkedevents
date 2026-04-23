from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models import DateField, Q
from django.db.models.functions import Coalesce, Greatest, TruncDate
from django.utils import timezone

from helevents.models import User
from registrations.models import SignUp


class Command(BaseCommand):
    help = "Delete users that have been inactive for a configurable number of years."

    def handle(self, *args, **options):
        now = timezone.now()

        deletion_years = settings.INACTIVE_USER_DELETION_YEARS
        if (
            isinstance(deletion_years, bool)
            or not isinstance(deletion_years, int)
            or deletion_years <= 0
        ):
            raise CommandError(
                f"INACTIVE_USER_DELETION_YEARS must be a positive integer, "
                f"got {deletion_years!r}."
            )

        threshold_date = (now - relativedelta(years=deletion_years)).date()

        candidates_qs = User.objects.annotate(
            last_activity=Coalesce(
                Greatest(
                    Coalesce("last_api_use", TruncDate("last_login")),
                    Coalesce(TruncDate("last_login"), "last_api_use"),
                    output_field=DateField(),
                ),
                TruncDate("date_joined"),
                output_field=DateField(),
            )
        ).filter(last_activity__lt=threshold_date)

        active_statuses = (
            SignUp.AttendeeStatus.ATTENDING,
            SignUp.AttendeeStatus.AWAITING_PAYMENT,
            SignUp.AttendeeStatus.WAITING_LIST,
        )

        has_active_signup = (
            # Contact person on a direct signup
            Q(
                contact_persons__deleted=False,
                contact_persons__signup__deleted=False,
                contact_persons__signup__attendee_status__in=active_statuses,
            )
            # Contact person on a signup group that has active signups
            | Q(
                contact_persons__deleted=False,
                contact_persons__signup_group__deleted=False,
                contact_persons__signup_group__signups__deleted=False,
                contact_persons__signup_group__signups__attendee_status__in=active_statuses,
            )
            # Creator of an active signup
            | Q(
                signup_created_by__deleted=False,
                signup_created_by__attendee_status__in=active_statuses,
            )
        )

        skipped_count = candidates_qs.filter(has_active_signup).distinct().count()
        deletable_qs = User.objects.filter(
            pk__in=candidates_qs.exclude(has_active_signup)
            .distinct()
            .values_list("pk", flat=True)
        )
        user_model_label = User._meta.label
        _, rows_by_model = deletable_qs.delete()
        deleted_count = rows_by_model.get(user_model_label, 0)

        self.stdout.write(
            self.style.SUCCESS(
                f"{deleted_count} inactive user(s) deleted, "
                f"{skipped_count} skipped due to active signups."
            )
        )
