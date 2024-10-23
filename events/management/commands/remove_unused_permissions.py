from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.management import BaseCommand
from django.db.models.functions import Greatest
from django.utils import timezone

from helevents.models import User
from registrations.models import RegistrationUserAccess


class Command(BaseCommand):
    help = "Remove unused admin and registration user permissions after expiration time has passed."  # noqa: E501

    @staticmethod
    def _handle_event_admins(datetime_now):
        admins_count = 0

        threshold_time = datetime_now - relativedelta(
            months=settings.EVENT_ADMIN_EXPIRATION_MONTHS
        )
        for user in User.objects.filter(
            last_login__lt=threshold_time, admin_organizations__isnull=False
        ):
            user.admin_organizations.clear()
            admins_count += 1

        return admins_count

    @staticmethod
    def _handle_financial_admins(datetime_now):
        admins_count = 0

        threshold_time = datetime_now - relativedelta(
            months=settings.FINANCIAL_ADMIN_EXPIRATION_MONTHS
        )
        for user in User.objects.filter(
            last_login__lt=threshold_time, financial_admin_organizations__isnull=False
        ):
            user.financial_admin_organizations.clear()
            admins_count += 1

        return admins_count

    @staticmethod
    def _handle_registration_admins(datetime_now):
        admins_count = 0

        threshold_time = datetime_now - relativedelta(
            months=settings.REGISTRATION_ADMIN_EXPIRATION_MONTHS
        )
        for user in User.objects.filter(
            last_login__lt=threshold_time,
            registration_admin_organizations__isnull=False,
        ):
            user.registration_admin_organizations.clear()
            admins_count += 1

        return admins_count

    @staticmethod
    def _handle_registration_users(datetime_now):
        registration_users_count = 0

        threshold_time = datetime_now - relativedelta(
            months=settings.REGISTRATION_USER_EXPIRATION_MONTHS
        )
        for registration_user in RegistrationUserAccess.objects.annotate(
            compare_time=Greatest(
                "registration__event__end_time",
                "registration__enrolment_end_time",
            )
        ).filter(compare_time__lt=threshold_time):
            registration_user.delete()
            registration_users_count += 1

        return registration_users_count

    def handle(self, *args, **options):
        now = timezone.now()

        event_admins = self._handle_event_admins(now)
        financial_admins = self._handle_financial_admins(now)
        registration_admins = self._handle_registration_admins(now)
        registration_users = self._handle_registration_users(now)

        self.stdout.write(
            self.style.SUCCESS(
                f"{event_admins} event admin, {financial_admins} financial admin, "
                f"{registration_admins} registration admin and {registration_users} "
                "registration user access permissions removed."
            )
        )
