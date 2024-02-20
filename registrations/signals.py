from typing import Union

from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from events.models import Event
from registrations.models import (
    Registration,
    RegistrationPriceGroup,
    SeatReservationCode,
    SignUp,
    SignUpContactPerson,
    SignUpGroup,
    SignUpNotificationType,
)
from registrations.utils import get_signup_create_url


def _create_signup_link_for_event(registration: Registration) -> None:
    registration.event.offers.filter(
        (Q(info_url_fi=None) | Q(info_url_fi=""))
        & (Q(info_url_sv=None) | Q(info_url_sv=""))
        & (Q(info_url_en=None) | Q(info_url_en=""))
    ).update(
        info_url_fi=get_signup_create_url(registration, "fi"),
        info_url_sv=get_signup_create_url(registration, "sv"),
        info_url_en=get_signup_create_url(registration, "en"),
    )


@transaction.atomic
def _recalculate_registration_capacities(registration_id: int) -> None:
    registration = (
        Registration.objects.filter(pk=registration_id).select_for_update().first()
    )

    registration.remaining_attendee_capacity = (
        registration.calculate_remaining_attendee_capacity()
    )
    registration.remaining_waiting_list_capacity = (
        registration.calculate_remaining_waiting_list_capacity()
    )

    registration._capacities_recalculation_save = True
    registration.save(
        update_fields=[
            "remaining_attendee_capacity",
            "remaining_waiting_list_capacity",
        ]
    )


def _send_event_cancellation_notification(event):
    is_recurring_sub_event_cancellation = (
        event.super_event_id is not None
        and event.super_event.super_event_type == Event.SuperEventType.RECURRING
        and getattr(event, "registration", None) is None
    )

    if is_recurring_sub_event_cancellation:
        # When a sub-event is cancelled, a registration might have been done to the super event
        # => notify that registration's contact person.
        qs_filter = Q(event_id=event.super_event_id)
    else:
        qs_filter = Q(event_id=event.pk)

    registration_ids = Registration.objects.filter(qs_filter).values_list(
        "pk", flat=True
    )

    for contact_person in SignUpContactPerson.objects.filter(
        Q(email__isnull=False)
        & ~Q(email="")
        & (
            Q(signup__registration_id__in=registration_ids)
            | Q(signup_group__registration_id__in=registration_ids)
        )
    ):
        contact_person.send_notification(
            SignUpNotificationType.EVENT_CANCELLATION,
            is_sub_event_cancellation=is_recurring_sub_event_cancellation,
        )


def _signup_or_group_post_delete(instance: Union[SignUp, SignUpGroup]) -> None:
    attendee_status = getattr(instance, "attendee_status", "")
    attending_signups = getattr(instance, "attending_signups", None)
    if attendee_status == SignUp.AttendeeStatus.ATTENDING or attending_signups:
        instance.registration.move_first_waitlisted_to_attending()

    contact_person = getattr(instance, "contact_person", None)
    if contact_person:
        contact_person.send_notification(SignUpNotificationType.CANCELLATION)

    transaction.on_commit(
        lambda: _recalculate_registration_capacities(instance.registration_id)
    )


@receiver(
    pre_save,
    sender=Event,
    dispatch_uid="notify_signups_on_event_cancellation_pre_save",
)
def notify_signups_on_event_cancellation_pre_save(
    sender: type[Event], instance: Event, **kwargs: dict
) -> None:
    if not (instance.pk and instance.event_status == Event.Status.CANCELLED):
        return

    old_instance = Event.objects.filter(pk=instance.pk).first()
    if old_instance and old_instance.event_status != instance.event_status:
        _send_event_cancellation_notification(instance)


@receiver(
    pre_save,
    sender=RegistrationPriceGroup,
    dispatch_uid="calculate_registration_price_group_vat_prices",
)
def calculate_registration_price_group_vat_prices(
    sender: type[RegistrationPriceGroup],
    instance: RegistrationPriceGroup,
    **kwargs: dict,
) -> None:
    instance.calculate_vat_and_price_without_vat()


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
        transaction.on_commit(lambda: _recalculate_registration_capacities(instance.pk))


@receiver(
    post_save,
    sender=SignUp,
    dispatch_uid="signup_post_save",
)
def signup_post_save(sender: type[SignUp], instance: SignUp, **kwargs: dict) -> None:
    transaction.on_commit(
        lambda: _recalculate_registration_capacities(instance.registration_id)
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
        lambda: _recalculate_registration_capacities(instance.registration_id)
    )


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


@receiver(
    post_save,
    sender=SeatReservationCode,
    dispatch_uid="seat_reservation_post_save",
)
def seat_reservation_post_save(
    sender: type[SeatReservationCode], instance: SeatReservationCode, **kwargs: dict
) -> None:
    transaction.on_commit(
        lambda: _recalculate_registration_capacities(instance.registration_id)
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
        lambda: _recalculate_registration_capacities(instance.registration_id)
    )
