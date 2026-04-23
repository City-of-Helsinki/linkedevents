import freezegun
import pytest
from dateutil.relativedelta import relativedelta
from django.conf import settings as django_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils.timezone import localtime

from helevents.models import User
from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.tests.factories import (
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
)


@pytest.mark.django_db
@pytest.mark.parametrize("bad_value", [0, -1, -10, 0.5, "5", None, True, False])
def test_delete_inactive_users_rejects_invalid_setting(settings, bad_value):
    settings.INACTIVE_USER_DELETION_YEARS = bad_value
    with pytest.raises(CommandError, match="INACTIVE_USER_DELETION_YEARS"):
        call_command("delete_inactive_users")


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
def test_delete_inactive_users_does_not_delete_user_active_on_threshold_date():
    """A user whose last_api_use is on the exact threshold date must not be deleted.

    last_api_use is a DateField. If it were cast to a datetime for comparison
    it would produce midnight UTC, which could be less than a threshold that
    includes a time-of-day component, causing premature deletion. The
    date-level comparison avoids this entirely.
    """
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS

    threshold_date = (now - relativedelta(years=expiration_years)).date()
    one_day_before = threshold_date - relativedelta(days=1)

    boundary_user = UserFactory(last_api_use=threshold_date)
    expired_user = UserFactory(last_api_use=one_day_before)

    call_command("delete_inactive_users")

    assert User.objects.filter(pk=boundary_user.pk).exists()
    assert not User.objects.filter(pk=expired_user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_delete_inactive_users_uses_most_recent_timestamp():
    """Most recent of last_api_use / last_login / date_joined wins."""
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS

    old_time = now - relativedelta(years=expiration_years + 1)
    recent_time = now - relativedelta(years=expiration_years, days=-1)

    # last_api_use is old, but last_login is recent → must NOT be deleted
    user = UserFactory(last_api_use=old_time, last_login=recent_time)

    call_command("delete_inactive_users")

    assert User.objects.filter(pk=user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
@pytest.mark.parametrize("field", ["last_login", "date_joined"])
def test_delete_inactive_users_falls_back_to_field_when_no_last_api_use(field):
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS

    expired_time = now - relativedelta(years=expiration_years + 1)
    active_time = now - relativedelta(years=expiration_years, days=-1)

    # Start with last_login=None so the date_joined variant is unambiguous;
    # the last_login variant overrides it via the field kwarg.
    base = {"last_api_use": None, "last_login": None}
    expired_user = UserFactory(**{**base, field: expired_time})
    active_user = UserFactory(**{**base, field: active_time})

    call_command("delete_inactive_users")

    assert not User.objects.filter(pk=expired_user.pk).exists()
    assert User.objects.filter(pk=active_user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
@pytest.mark.parametrize(
    "attendee_status",
    [
        SignUp.AttendeeStatus.ATTENDING,
        SignUp.AttendeeStatus.AWAITING_PAYMENT,
        SignUp.AttendeeStatus.WAITING_LIST,
    ],
)
def test_delete_inactive_users_skips_user_with_active_signup_as_contact_person(
    attendee_status,
):
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS
    expired_time = now - relativedelta(years=expiration_years + 1)

    user_with_signup = UserFactory(last_api_use=expired_time)
    user_without_signup = UserFactory(last_api_use=expired_time)

    signup = SignUpFactory(attendee_status=attendee_status)
    SignUpContactPersonFactory(signup=signup, user=user_with_signup)

    call_command("delete_inactive_users")

    # User linked as contact person to an active signup must be preserved
    assert User.objects.filter(pk=user_with_signup.pk).exists()
    # User with no active signup must be deleted
    assert not User.objects.filter(pk=user_without_signup.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
@pytest.mark.parametrize(
    "attendee_status",
    [
        SignUp.AttendeeStatus.ATTENDING,
        SignUp.AttendeeStatus.AWAITING_PAYMENT,
        SignUp.AttendeeStatus.WAITING_LIST,
    ],
)
def test_delete_inactive_users_skips_user_who_is_contact_person_for_signup_group(
    attendee_status,
):
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS
    expired_time = now - relativedelta(years=expiration_years + 1)

    user_with_group = UserFactory(last_api_use=expired_time)
    user_without_group = UserFactory(last_api_use=expired_time)

    group = SignUpGroupFactory()
    SignUpFactory(
        signup_group=group,
        attendee_status=attendee_status,
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
@pytest.mark.parametrize(
    "attendee_status",
    [
        SignUp.AttendeeStatus.ATTENDING,
        SignUp.AttendeeStatus.AWAITING_PAYMENT,
        SignUp.AttendeeStatus.WAITING_LIST,
    ],
)
def test_delete_inactive_users_skips_user_who_created_active_signup(attendee_status):
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS
    expired_time = now - relativedelta(years=expiration_years + 1)

    creator = UserFactory(last_api_use=expired_time)
    other_user = UserFactory(last_api_use=expired_time)

    SignUpFactory(
        created_by=creator,
        attendee_status=attendee_status,
    )

    call_command("delete_inactive_users")

    # Creator of an active signup must be preserved
    assert User.objects.filter(pk=creator.pk).exists()
    # Unrelated user must be deleted
    assert not User.objects.filter(pk=other_user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
@pytest.mark.parametrize(
    "attendee_status",
    [
        SignUp.AttendeeStatus.ATTENDING,
        SignUp.AttendeeStatus.AWAITING_PAYMENT,
        SignUp.AttendeeStatus.WAITING_LIST,
    ],
)
def test_delete_inactive_users_deletes_user_with_soft_deleted_signup_as_contact_person(
    attendee_status,
):
    """Soft-deleted signups must not protect a user from deletion."""
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS
    expired_time = now - relativedelta(years=expiration_years + 1)

    user = UserFactory(last_api_use=expired_time)

    signup = SignUpFactory(attendee_status=attendee_status)
    SignUpContactPersonFactory(signup=signup, user=user)
    signup.soft_delete()

    call_command("delete_inactive_users")

    assert not User.objects.filter(pk=user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
@pytest.mark.parametrize(
    "attendee_status",
    [
        SignUp.AttendeeStatus.ATTENDING,
        SignUp.AttendeeStatus.AWAITING_PAYMENT,
        SignUp.AttendeeStatus.WAITING_LIST,
    ],
)
def test_delete_inactive_users_deletes_user_with_soft_deleted_signup_group(
    attendee_status,
):
    """Soft-deleted signup groups must not protect a user from deletion."""
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS
    expired_time = now - relativedelta(years=expiration_years + 1)

    user = UserFactory(last_api_use=expired_time)

    group = SignUpGroupFactory()
    SignUpFactory(
        signup_group=group,
        attendee_status=attendee_status,
    )
    SignUpContactPersonFactory(signup_group=group, signup=None, user=user)
    group.soft_delete()

    call_command("delete_inactive_users")

    assert not User.objects.filter(pk=user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_delete_inactive_users_deletes_user_with_only_cancelled_signup():
    """A soft-deleted (cancelled) signup via created_by must not protect the user."""
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS
    expired_time = now - relativedelta(years=expiration_years + 1)

    user = UserFactory(last_api_use=expired_time)
    # Signups are hard-deleted when cancelled; simulate a previously active
    # signup that was cancelled by creating one and soft-deleting it via
    # created_by, so the created_by guard is exercised.
    signup = SignUpFactory(
        created_by=user,
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    signup.soft_delete()

    call_command("delete_inactive_users")

    assert not User.objects.filter(pk=user.pk).exists()


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_kwargs",
    [
        {"is_superuser": True, "is_staff": True},
        {"is_superuser": False, "is_staff": True},
    ],
    ids=["superuser", "staff"],
)
def test_delete_inactive_users_deletes_inactive_privileged_users(user_kwargs):
    """Superuser and staff accounts are intentionally deleted after inactivity.
    Privileged users log in via Django Admin, which only updates last_login
    (not last_api_use), so last_login is used as the activity timestamp here.
    """
    now = localtime()
    expiration_years = django_settings.INACTIVE_USER_DELETION_YEARS
    expired_time = now - relativedelta(years=expiration_years + 1)
    active_time = now - relativedelta(years=expiration_years, days=-1)

    inactive_user = UserFactory(
        last_api_use=None, last_login=expired_time, **user_kwargs
    )
    active_user = UserFactory(last_api_use=None, last_login=active_time, **user_kwargs)

    call_command("delete_inactive_users")

    assert not User.objects.filter(pk=inactive_user.pk).exists()
    assert User.objects.filter(pk=active_user.pk).exists()
