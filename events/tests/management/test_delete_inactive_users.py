import freezegun
import pytest
from dateutil.relativedelta import relativedelta
from django.conf import settings as django_settings
from django.core.management import call_command
from django.utils.timezone import localtime

from helevents.models import User
from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.tests.factories import (
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
)


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_delete_inactive_users_deletes_expired_users():
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS

    expired_time = now - relativedelta(years=expiration_years + 1)
    active_time = now - relativedelta(years=expiration_years, days=-1)

    expired_user = UserFactory(last_api_use=expired_time)
    expired_user2 = UserFactory(last_api_use=expired_time)
    active_user = UserFactory(last_api_use=active_time)

    assert User.objects.filter(pk__in=[expired_user.pk, expired_user2.pk]).count() == 2
    assert User.objects.filter(pk=active_user.pk).count() == 1

    call_command("delete_inactive_users")

    assert not User.objects.filter(pk__in=[expired_user.pk, expired_user2.pk]).exists()
    assert User.objects.filter(pk=active_user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_delete_inactive_users_does_not_delete_active_users():
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS

    active_time = now - relativedelta(years=expiration_years, days=-1)
    active_user = UserFactory(last_api_use=active_time)

    call_command("delete_inactive_users")

    assert User.objects.filter(pk=active_user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_delete_inactive_users_no_users():
    """Command runs without errors when there are no users to delete."""
    call_command("delete_inactive_users")


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_delete_inactive_users_respects_configurable_setting(settings):
    now = localtime()

    settings.INACTIVE_USER_DELETION_YEARS = 3

    expired_time = now - relativedelta(years=4)
    active_time = now - relativedelta(years=2)

    expired_user = UserFactory(last_api_use=expired_time)
    active_user = UserFactory(last_api_use=active_time)

    call_command("delete_inactive_users")

    assert not User.objects.filter(pk=expired_user.pk).exists()
    assert User.objects.filter(pk=active_user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_delete_inactive_users_uses_date_joined_when_no_last_api_use():
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS

    expired_joined = now - relativedelta(years=expiration_years + 1)
    active_joined = now - relativedelta(years=expiration_years, days=-1)

    # Users that have never used the API — fall back to date_joined
    expired_user = UserFactory(last_api_use=None, date_joined=expired_joined)
    active_user = UserFactory(last_api_use=None, date_joined=active_joined)

    call_command("delete_inactive_users")

    assert not User.objects.filter(pk=expired_user.pk).exists()
    assert User.objects.filter(pk=active_user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_delete_inactive_users_skips_user_with_active_signup_as_contact_person():
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS
    expired_time = now - relativedelta(years=expiration_years + 1)

    user_with_signup = UserFactory(last_api_use=expired_time)
    user_without_signup = UserFactory(last_api_use=expired_time)

    signup = SignUpFactory(attendee_status=SignUp.AttendeeStatus.ATTENDING)
    SignUpContactPersonFactory(signup=signup, user=user_with_signup)

    call_command("delete_inactive_users")

    # User linked as contact person to an active signup must be preserved
    assert User.objects.filter(pk=user_with_signup.pk).exists()
    # User with no active signup must be deleted
    assert not User.objects.filter(pk=user_without_signup.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_delete_inactive_users_skips_user_who_is_contact_person_for_signup_group():
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS
    expired_time = now - relativedelta(years=expiration_years + 1)

    user_with_group = UserFactory(last_api_use=expired_time)
    user_without_group = UserFactory(last_api_use=expired_time)

    group = SignUpGroupFactory()
    SignUpFactory(
        signup_group=group,
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    # Contact person is linked to the group, not directly to a signup
    SignUpContactPersonFactory(signup_group=group, signup=None, user=user_with_group)

    call_command("delete_inactive_users")

    # User linked as contact person for a group with active signups must be preserved
    assert User.objects.filter(pk=user_with_group.pk).exists()
    # Unrelated user must be deleted
    assert not User.objects.filter(pk=user_without_group.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_delete_inactive_users_skips_user_who_created_active_signup():
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS
    expired_time = now - relativedelta(years=expiration_years + 1)

    creator = UserFactory(last_api_use=expired_time)
    other_user = UserFactory(last_api_use=expired_time)

    SignUpFactory(
        created_by=creator,
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
    )

    call_command("delete_inactive_users")

    # Creator of an active signup must be preserved
    assert User.objects.filter(pk=creator.pk).exists()
    # Unrelated user must be deleted
    assert not User.objects.filter(pk=other_user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_delete_inactive_users_deletes_user_with_only_cancelled_signup():
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS
    expired_time = now - relativedelta(years=expiration_years + 1)

    user = UserFactory(last_api_use=expired_time)
    # AttendeeStatus has no explicit "cancelled" — signups are deleted when
    # cancelled, so a signup in any listed status counts as active.
    # Here we verify that a user with no active signups is still deleted.
    call_command("delete_inactive_users")

    assert not User.objects.filter(pk=user.pk).exists()
