from typing import Union

from django.db.models.signals import post_delete
from django.dispatch import receiver

from registrations.models import SignUp, SignUpGroup
from registrations.notifications import SignUpNotificationType


def _signup_or_group_post_delete(instance: Union[SignUp, SignUpGroup]) -> None:
    instance.send_notification(SignUpNotificationType.CANCELLATION)

    attendee_status = getattr(instance, "attendee_status", "")
    attending_signups = getattr(instance, "attending_signups", None)
    if attendee_status == SignUp.AttendeeStatus.ATTENDING or attending_signups:
        instance.registration.move_first_waitlisted_to_attending()


@receiver(
    post_delete,
    sender=SignUp,
    dispatch_uid="signup_post_delete",
)
def signup_post_delete(sender: type[SignUp], instance: SignUp, **kwargs: dict) -> None:
    if getattr(instance, "_individually_deleted", False):
        _signup_or_group_post_delete(instance)


@receiver(
    post_delete,
    sender=SignUpGroup,
    dispatch_uid="signup_group_post_delete",
)
def signup_group_post_delete(
    sender: type[SignUpGroup], instance: SignUpGroup, **kwargs: dict
) -> None:
    _signup_or_group_post_delete(instance)
