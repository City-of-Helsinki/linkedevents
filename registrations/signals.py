from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from registrations.models import Registration, SeatReservationCode, SignUp, SignUpGroup
from registrations.utils import get_signup_create_url
from registrations.utils.registration import recalculate_registration_capacities


def _create_signup_link_for_event(registration: Registration) -> None:
    registration.event.offers.update(
        info_url_fi=get_signup_create_url(registration, "fi"),
        info_url_sv=get_signup_create_url(registration, "sv"),
        info_url_en=get_signup_create_url(registration, "en"),
    )


@receiver(
    post_save,
    sender=Registration,
    dispatch_uid="registration_post_save",
)
def registration_post_save(
    sender: type[Registration], instance: Registration, **kwargs: dict
) -> None:
    if kwargs.get("created"):
        _create_signup_link_for_event(instance)

    update_fields = kwargs.get("update_fields")
    if not getattr(instance, "_capacities_recalculation_save", False) and (
        update_fields is None
        or "maximum_attendee_capacity" in update_fields
        or "waiting_list_capacity" in update_fields
    ):
        transaction.on_commit(lambda: recalculate_registration_capacities(instance.pk))


@receiver(
    post_save,
    sender=SignUp,
    dispatch_uid="signup_post_save",
)
def signup_post_save(sender: type[SignUp], instance: SignUp, **kwargs: dict) -> None:
    transaction.on_commit(
        lambda: recalculate_registration_capacities(instance.registration_id)
    )


@receiver(
    post_save,
    sender=SignUpGroup,
    dispatch_uid="signup_group_post_save",
)
def signup_group_post_save(
    sender: type[SignUpGroup], instance: SignUpGroup, **kwargs: dict
) -> None:
    transaction.on_commit(
        lambda: recalculate_registration_capacities(instance.registration_id)
    )


@receiver(
    post_delete,
    sender=SignUp,
    dispatch_uid="signup_post_delete",
)
def signup_post_delete(sender: type[SignUp], instance: SignUp, **kwargs: dict) -> None:
    if getattr(instance, "_individually_deleted", False):
        transaction.on_commit(
            lambda: recalculate_registration_capacities(instance.registration_id)
        )


@receiver(
    post_delete,
    sender=SignUpGroup,
    dispatch_uid="signup_group_post_delete",
)
def signup_group_post_delete(
    sender: type[SignUpGroup], instance: SignUpGroup, **kwargs: dict
) -> None:
    transaction.on_commit(
        lambda: recalculate_registration_capacities(instance.registration_id)
    )


@receiver(
    post_save,
    sender=SeatReservationCode,
    dispatch_uid="seat_reservation_post_save",
)
def seat_reservation_post_save(
    sender: type[SeatReservationCode], instance: SeatReservationCode, **kwargs: dict
) -> None:
    transaction.on_commit(
        lambda: recalculate_registration_capacities(instance.registration_id)
    )


@receiver(
    post_delete,
    sender=SeatReservationCode,
    dispatch_uid="seat_reservation_post_delete",
)
def seat_reservation_post_delete(
    sender: type[SeatReservationCode], instance: SeatReservationCode, **kwargs: dict
) -> None:
    transaction.on_commit(
        lambda: recalculate_registration_capacities(instance.registration_id)
    )
