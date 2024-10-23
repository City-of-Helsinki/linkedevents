from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from helsinki_gdpr.types import Error, ErrorResponse

from registrations.models import SignUpGroup, SignUpPayment


def get_user_for_gdpr_api(user: get_user_model()) -> get_user_model():
    """
    Function used by the Helsinki Profile GDPR API to get the "user" instance from the "GDPR Model"
    instance. Since in our case the GDPR Model and the user are one and the same, we simply return
    the same User instance that is given as a parameter.

    :param user: the User instance whose GDPR data is being queried
    :return: the same User instance
    """  # noqa: E501
    return user


def delete_user_and_gdpr_data(
    user: get_user_model(), dry_run: bool
) -> Optional[ErrorResponse]:
    """
    Function used by the Helsinki Profile GDPR API to delete all GDPR data collected of the user.
    The GDPR API package will run this within a transaction.

    **Note!**: Disabled the deletion for now until the two service problem is solved.

    :param  user: the User instance to be deleted along with related GDPR data
    :param dry_run: a boolean telling if this is a dry run of the function or not
    """  # noqa: E501

    if settings.GDPR_DISABLE_API_DELETION:
        # Delete user is disabled. Returns 403 FORBIDDEN so that the GDPR view
        # handles it correctly.
        return ErrorResponse(
            [
                Error(
                    "GDPR_DISABLE_API_DELETION=1",
                    {
                        "fi": "GDPR poistopyynnöt on estetty toistaiseksi Linked Events -palvelussa",  # noqa: E501
                        "en": "GDPR removal requests are temporarily unavailable in Linked Events",  # noqa: E501
                        "sv": "GDPR-borttagning begäran är tillfälligt inte tillgänglig i Linked Events",  # noqa: E501
                    },
                )
            ]
        )

    minimum_event_end = timezone.now() - timezone.timedelta(
        days=settings.GDPR_API_DELETE_EVENT_END_THRESHOLD_DAYS
    )
    upcoming_query = Q(
        signup_group__registration__event__end_time__gt=minimum_event_end
    ) | Q(registration__event__end_time__gt=minimum_event_end)
    has_upcoming_signups = user.signup_created_by.filter(upcoming_query).exists()

    if has_upcoming_signups:
        return ErrorResponse(
            [
                Error(
                    "UPCOMING_SIGNUPS",
                    {
                        "fi": "Käyttäjällä on tulevia ilmoittautumisia, joten tietoja ei voida poistaa.",  # noqa: E501
                        "en": "User has upcoming signups, so data cannot be deleted.",
                        "sv": "Användaren har kommande registreringar, så data kan inte raderas.",  # noqa: E501
                    },
                )
            ]
        )

    ongoing_statuses = (
        SignUpPayment.PaymentStatus.CANCELLED,
        SignUpPayment.PaymentStatus.REFUNDED,
        SignUpPayment.PaymentStatus.CREATED,
    )
    signups = user.signup_created_by.all()
    signup_groups = SignUpGroup.objects.filter(signups__in=signups)

    has_ongoing_payments = (
        user.signuppayment_created_by.filter(status__in=ongoing_statuses).exists()
        or signup_groups.filter(payment__status__in=ongoing_statuses).exists()
    )

    if has_ongoing_payments:
        return ErrorResponse(
            [
                Error(
                    "ONGOING_PAYMENTS",
                    {
                        "fi": "Käyttäjällä on avoimia maksuja, joten tietoja ei voida poistaa.",  # noqa: E501
                        "en": "User has ongoing payments, so data cannot be deleted.",
                        "sv": "Användaren har pågående betalningar, så data kan inte raderas.",  # noqa: E501
                    },
                )
            ]
        )

    for signup in user.signup_created_by.filter(signup_group_id__isnull=True):
        signup._individually_deleted = (
            True  # post_delete signal function will check this
        )
        signup.delete()

    user.signupgroup_created_by.all().delete()

    user.events_event_created_by.filter(user_email=user.email).update(
        user_email=None,
        user_name=None,
        user_phone_number=None,
        user_organization=None,
    )

    user.delete()
