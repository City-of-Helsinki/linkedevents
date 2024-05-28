from datetime import datetime

import freezegun
import pytest
from dateutil.relativedelta import relativedelta
from django.conf import settings as django_settings
from django.core.management import call_command
from django.utils.timezone import localtime

from helevents.tests.factories import UserFactory
from registrations.models import RegistrationUserAccess
from registrations.tests.factories import RegistrationUserAccessFactory


def _test_remove_unused_admin_permissions(
    organization, organization2, admin_relation: str, expiration_months: int
):
    now = localtime()

    expired_months_ago = now - relativedelta(months=expiration_months + 1)
    active_months_ago = now - relativedelta(months=expiration_months, days=-1)

    expired_admin = UserFactory(last_login=expired_months_ago)
    getattr(expired_admin, admin_relation).add(organization)

    expired_admin2 = UserFactory(last_login=expired_months_ago)
    getattr(expired_admin2, admin_relation).add(organization)
    getattr(expired_admin2, admin_relation).add(organization2)

    active_admin = UserFactory(last_login=active_months_ago)
    getattr(active_admin, admin_relation).add(organization)

    assert getattr(expired_admin, admin_relation).count() == 1
    assert getattr(expired_admin2, admin_relation).count() == 2
    assert getattr(active_admin, admin_relation).count() == 1

    call_command("remove_unused_permissions")

    expired_admin.refresh_from_db()
    assert getattr(expired_admin, admin_relation).count() == 0

    expired_admin2.refresh_from_db()
    assert getattr(expired_admin2, admin_relation).count() == 0

    active_admin.refresh_from_db()
    assert getattr(active_admin, admin_relation).count() == 1


def _set_registration_comparison_datetimes(
    registration, expiration_comparison_source: str, n_months_ago: datetime
):
    if expiration_comparison_source == "registration":
        registration.enrolment_end_time = n_months_ago
        registration.save(update_fields=["enrolment_end_time"])

        registration.event.start_time = n_months_ago - relativedelta(days=2)
        registration.event.end_time = n_months_ago - relativedelta(days=1)
        registration.event.save(update_fields=["start_time", "end_time"])
    else:
        registration.enrolment_end_time = n_months_ago - relativedelta(days=1)
        registration.save(update_fields=["enrolment_end_time"])

        registration.event.start_time = n_months_ago - relativedelta(days=1)
        registration.event.end_time = n_months_ago
        registration.event.save(update_fields=["start_time", "end_time"])


def _test_remove_unused_registration_user_permissions(
    registration, registration2, registration3, expiration_comparison_source
):
    now = localtime()
    expiration_months = django_settings.REGISTRATION_USER_EXPIRATION_MONTHS

    expired_months_ago = now - relativedelta(months=expiration_months + 1)
    active_months_ago = now - relativedelta(months=expiration_months, days=-1)

    RegistrationUserAccessFactory(registration=registration, email="expired@test.com")
    _set_registration_comparison_datetimes(
        registration, expiration_comparison_source, expired_months_ago
    )

    RegistrationUserAccessFactory(
        registration=registration2, email="expired2@hel.fi", is_substitute_user=True
    )
    _set_registration_comparison_datetimes(
        registration2, expiration_comparison_source, expired_months_ago
    )

    active_user_access = RegistrationUserAccessFactory(
        registration=registration3, email="active@test.com"
    )
    _set_registration_comparison_datetimes(
        registration3, expiration_comparison_source, active_months_ago
    )

    assert RegistrationUserAccess.objects.count() == 3

    call_command("remove_unused_permissions")

    assert RegistrationUserAccess.objects.count() == 1
    assert RegistrationUserAccess.objects.first().pk == active_user_access.pk


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_remove_unused_event_admin_permissions(organization, organization2):
    _test_remove_unused_admin_permissions(
        organization,
        organization2,
        "admin_organizations",
        expiration_months=django_settings.EVENT_ADMIN_EXPIRATION_MONTHS,
    )


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_remove_unused_financial_admin_permissions(organization, organization2):
    _test_remove_unused_admin_permissions(
        organization,
        organization2,
        "financial_admin_organizations",
        expiration_months=django_settings.FINANCIAL_ADMIN_EXPIRATION_MONTHS,
    )


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_remove_unused_registration_admin_permissions(organization, organization2):
    _test_remove_unused_admin_permissions(
        organization,
        organization2,
        "registration_admin_organizations",
        expiration_months=django_settings.REGISTRATION_ADMIN_EXPIRATION_MONTHS,
    )


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_remove_unused_registration_user_permissions_based_on_event_end_time(
    registration, registration2, registration3
):
    _test_remove_unused_registration_user_permissions(
        registration, registration2, registration3, "event"
    )


@freezegun.freeze_time("2024-05-28 03:30:00+03:00")
@pytest.mark.django_db
def test_remove_unused_registration_user_permissions_based_on_registration_end_time(
    registration, registration2, registration3
):
    _test_remove_unused_registration_user_permissions(
        registration, registration2, registration3, "registration"
    )
