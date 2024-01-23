from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response


def get_user_for_gdpr_api(user: get_user_model()) -> get_user_model():
    """
    Function used by the Helsinki Profile GDPR API to get the "user" instance from the "GDPR Model"
    instance. Since in our case the GDPR Model and the user are one and the same, we simply return
    the same User instance that is given as a parameter.

    :param user: the User instance whose GDPR data is being queried
    :return: the same User instance
    """
    return user


def delete_user_and_gdpr_data(user: get_user_model(), dry_run: bool) -> None:
    """
    Function used by the Helsinki Profile GDPR API to delete all GDPR data collected of the user.
    The GDPR API package will run this within a transaction.

    **Note!**: Disabled the deletion for now until the two service problem is solved.

    :param  user: the User instance to be deleted along with related GDPR data
    :param dry_run: a boolean telling if this is a dry run of the function or not
    """

    if settings.GDPR_DISABLE_API_DELETION:
        # Delete user is disabled. Returns 403 FORBIDDEN so that the GDPR view handles it correctly.
        return Response(status=status.HTTP_403_FORBIDDEN)

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
