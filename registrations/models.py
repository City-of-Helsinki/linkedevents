from datetime import timedelta
from smtplib import SMTPException
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.mail import send_mail
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import DateTimeField, ExpressionWrapper, F, Sum
from django.forms.fields import MultipleChoiceField
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.functional import cached_property
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override

from events.models import Event, Language
from registrations.utils import (
    code_validity_duration,
    get_email_noreply_address,
    get_ui_locales,
)

User = settings.AUTH_USER_MODEL


class SignUpNotificationType:
    CANCELLATION = "cancellation"
    CONFIRMATION = "confirmation"
    CONFIRMATION_TO_WAITING_LIST = "confirmation_to_waiting_list"
    TRANSFERRED_AS_PARTICIPANT = "transferred_as_participant"


class MandatoryFields(models.TextChoices):
    """Choices for mandatory fields on SignUp model."""

    CITY = "city", _("City")
    FIRST_NAME = "first_name", _("First name")
    LAST_NAME = "last_name", _("Last name")
    PHONE_NUMBER = "phone_number", _("Phone number")
    STREET_ADDRESS = "street_address", _("Street address")
    ZIPCODE = "zipcode", _("ZIP code")


# https://gist.github.com/danni/f55c4ce19598b2b345ef?permalink_comment_id=4448023#gistcomment-4448023
class _MultipleChoiceField(MultipleChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs.pop("base_field", None)
        kwargs.pop("max_length", None)
        super().__init__(*args, **kwargs)


# https://gist.github.com/danni/f55c4ce19598b2b345ef?permalink_comment_id=4448023#gistcomment-4448023
class ChoiceArrayField(ArrayField):
    """
    A field that allows to store an array of choices.

    Uses Django postgres ArrayField
    and a _MultipleChoiceField for its formfield.
    """

    def formfield(self, **kwargs):
        return super().formfield(
            **{
                "form_class": _MultipleChoiceField,
                "choices": self.base_field.choices,
                **kwargs,
            }
        )


class CreatedModifiedBaseModel(models.Model):
    created_at = models.DateTimeField(
        verbose_name=_("Created at"),
        null=False,
        blank=True,
        auto_now_add=True,
    )
    last_modified_at = models.DateTimeField(
        verbose_name=_("Modified at"),
        null=False,
        blank=True,
        auto_now=True,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created_by",
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_last_modified_by",
    )

    class Meta:
        abstract = True


class Registration(CreatedModifiedBaseModel):
    event = models.OneToOneField(
        Event,
        on_delete=models.CASCADE,
        related_name="registration",
        null=False,
        blank=True,
    )
    attendee_registration = models.BooleanField(default=False, null=False)
    audience_min_age = models.PositiveSmallIntegerField(
        verbose_name=_("Minimum recommended age"), blank=True, null=True, db_index=True
    )
    audience_max_age = models.PositiveSmallIntegerField(
        verbose_name=_("Maximum recommended age"), blank=True, null=True, db_index=True
    )

    enrolment_start_time = models.DateTimeField(
        verbose_name=_("Enrollment start time"), blank=True, null=True
    )
    enrolment_end_time = models.DateTimeField(
        verbose_name=_("Enrollment end time"), blank=True, null=True
    )

    confirmation_message = models.TextField(
        verbose_name=_("Confirmation message"), blank=True, null=True
    )
    instructions = models.TextField(
        verbose_name=_("Instructions"), blank=True, null=True
    )

    maximum_attendee_capacity = models.PositiveSmallIntegerField(
        verbose_name=_("Maximum attendee capacity"), null=True, blank=True
    )
    minimum_attendee_capacity = models.PositiveSmallIntegerField(
        verbose_name=_("Minimum attendee capacity"), null=True, blank=True
    )
    waiting_list_capacity = models.PositiveSmallIntegerField(
        verbose_name=_("Waiting list capacity"), null=True, blank=True
    )
    maximum_group_size = models.PositiveSmallIntegerField(
        verbose_name=_("Maximum group size"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )

    mandatory_fields = ChoiceArrayField(
        models.CharField(
            max_length=16,
            choices=MandatoryFields.choices,
            blank=True,
        ),
        default=list,
        blank=True,
        verbose_name=_("Mandatory fields"),
    )

    @property
    def data_source(self):
        return self.event.data_source

    @property
    def publisher(self):
        return self.event.publisher

    @cached_property
    def reserved_seats_amount(self):
        return (
            # Calculate expiration time for each reservation
            self.reservations.annotate(
                expiration=ExpressionWrapper(
                    F("timestamp")
                    + timedelta(minutes=1) * code_validity_duration(F("seats")),
                    output_field=DateTimeField(),
                )
            )
            # Filter to get all not expired reservations
            .filter(expiration__gte=localtime())
            # Sum  seats of not expired reservation
            .aggregate(seats_sum=Sum("seats", output_field=models.IntegerField()))[
                "seats_sum"
            ]
            or 0
        )

    @cached_property
    def current_attendee_count(self):
        return self.signups.filter(
            attendee_status=SignUp.AttendeeStatus.ATTENDING
        ).count()

    @cached_property
    def current_waiting_list_count(self):
        return self.signups.filter(
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST
        ).count()

    @property
    def remaining_attendee_capacity(self):
        maximum_attendee_capacity = self.maximum_attendee_capacity

        if maximum_attendee_capacity is None:
            return None

        attendee_count = self.current_attendee_count
        reserved_seats_amount = self.reserved_seats_amount

        return max(
            maximum_attendee_capacity - attendee_count - reserved_seats_amount, 0
        )

    @property
    def remaining_waiting_list_capacity(self):
        waiting_list_capacity = self.waiting_list_capacity

        if waiting_list_capacity is None:
            return None

        waiting_list_count = self.current_waiting_list_count
        reserved_seats_amount = self.reserved_seats_amount
        maximum_attendee_capacity = self.maximum_attendee_capacity

        if maximum_attendee_capacity is not None:
            # Calculate the amount of reserved seats that are used for actual seats
            # and reduce it from reserved_seats_amount to get amount of reserved seats
            # in the waiting list
            attendee_count = self.current_attendee_count
            reserved_seats_amount = max(
                reserved_seats_amount
                - max(maximum_attendee_capacity - attendee_count, 0),
                0,
            )

        return max(
            waiting_list_capacity - waiting_list_count - reserved_seats_amount, 0
        )

    def can_be_edited_by(self, user):
        """Check if current registration can be edited by the given user"""
        if user.is_superuser:
            return True
        return user.is_admin_of(self.event.publisher)

    def is_user_editable_resources(self):
        return bool(
            self.event.data_source and self.event.data_source.user_editable_resources
        )


class RegistrationUser(models.Model):
    email = models.EmailField(verbose_name=_("E-mail"))

    registration = models.ForeignKey(
        Registration, on_delete=models.CASCADE, related_name="registration_users"
    )
    language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registration_user_language",
    )

    def can_be_edited_by(self, user):
        """Check if current registration user can be edited by the given user"""
        if user.is_superuser:
            return True
        return user.is_admin_of(self.registration.event.publisher)

    def _get_language_pk(self):
        if self.language:
            return self.language.pk
        return "fi"

    def send_invitation(self):
        locale = self._get_language_pk()

        with translation.override(locale):
            event_name = self.registration.event.name
            event_type_id = self.registration.event.type_id

            email_variables = {
                "email": self.email,
                "event": event_name,
                "event_type_id": event_type_id,
                "linked_events_ui_locale": locale,
                "linked_events_ui_url": settings.LINKED_EVENTS_UI_URL,
                "linked_registrations_ui_locale": locale,
                "linked_registrations_ui_url": settings.LINKED_REGISTRATIONS_UI_URL,
                "registration_id": self.registration.id,
            }

            invitation_template = "signup_list_rights_granted.html"
            invitation_subject = _(
                "Rights granted to the participant list - %(event_name)s"
            ) % {"event_name": event_name}

            rendered_body = render_to_string(invitation_template, email_variables)

        try:
            send_mail(
                invitation_subject,
                rendered_body,
                get_email_noreply_address(),
                [self.email],
                html_message=rendered_body,
            )
        except SMTPException:
            pass

    class Meta:
        unique_together = ("email", "registration")


class SignUp(CreatedModifiedBaseModel):
    class AttendeeStatus:
        WAITING_LIST = "waitlisted"
        ATTENDING = "attending"

    ATTENDEE_STATUSES = (
        (AttendeeStatus.WAITING_LIST, _("Waitlisted")),
        (AttendeeStatus.ATTENDING, _("Attending")),
    )

    class NotificationType:
        NO_NOTIFICATION = "none"
        SMS = "sms"
        EMAIL = "email"
        SMS_EMAIL = "sms and email"

    NOTIFICATION_TYPES = (
        (NotificationType.NO_NOTIFICATION, _("No Notification")),
        (NotificationType.SMS, _("SMS")),
        (NotificationType.EMAIL, _("E-Mail")),
        (NotificationType.SMS_EMAIL, _("Both SMS and email.")),
    )

    class PresenceStatus:
        NOT_PRESENT = "not_present"
        PRESENT = "present"

    PRESENCE_STATUSES = (
        (PresenceStatus.NOT_PRESENT, _("Not present")),
        (PresenceStatus.PRESENT, _("Present")),
    )

    registration = models.ForeignKey(
        Registration, on_delete=models.PROTECT, related_name="signups"
    )
    first_name = models.CharField(
        verbose_name=_("First name"),
        max_length=50,
        blank=True,
        null=True,
        default=None,
    )
    last_name = models.CharField(
        verbose_name=_("Last name"),
        max_length=50,
        blank=True,
        null=True,
        default=None,
    )
    date_of_birth = models.DateField(
        verbose_name=_("Date of birth"), blank=True, null=True
    )
    city = models.CharField(
        verbose_name=_("City"),
        max_length=50,
        blank=True,
        null=True,
        default=None,
    )
    email = models.EmailField(
        verbose_name=_("E-mail"), blank=True, null=True, default=None
    )
    extra_info = models.TextField(
        verbose_name=_("Extra info"),
        blank=True,
        null=True,
        default=None,
    )
    membership_number = models.CharField(
        verbose_name=_("Membership number"),
        max_length=50,
        blank=True,
        null=True,
        default=None,
    )
    phone_number = models.CharField(
        verbose_name=_("Phone number"),
        max_length=18,
        blank=True,
        null=True,
        default=None,
    )
    notifications = models.CharField(
        verbose_name=_("Notification type"),
        max_length=25,
        choices=NOTIFICATION_TYPES,
        default=NotificationType.NO_NOTIFICATION,
    )
    attendee_status = models.CharField(
        verbose_name=_("Attendee status"),
        max_length=25,
        choices=ATTENDEE_STATUSES,
        default=AttendeeStatus.ATTENDING,
    )
    native_language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signup_native_language",
    )
    service_language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signup_service_language",
    )
    street_address = models.CharField(
        verbose_name=_("Street address"),
        max_length=500,
        blank=True,
        null=True,
        default=None,
    )
    zipcode = models.CharField(
        verbose_name=_("ZIP code"),
        max_length=10,
        blank=True,
        null=True,
        default=None,
    )

    presence_status = models.CharField(
        verbose_name=_("Presence status"),
        max_length=25,
        choices=PRESENCE_STATUSES,
        default=PresenceStatus.NOT_PRESENT,
    )

    @property
    def data_source(self):
        return self.registration.data_source

    @property
    def publisher(self):
        return self.registration.publisher

    def can_be_edited_by(self, user):
        """Check if current signup can be edited by the given user"""
        return (
            user.is_superuser
            or user.is_admin_of(self.publisher)
            or user.id == self.created_by_id
        )

    def is_user_editable_resources(self):
        return bool(self.data_source and self.data_source.user_editable_resources)

    def get_service_language_pk(self):
        if self.service_language:
            return self.service_language.pk
        return "fi"

    def send_notification(self, notification_type):
        [linked_events_ui_locale, linked_registrations_ui_locale] = get_ui_locales(
            self.service_language
        )

        with translation.override(self.get_service_language_pk()):
            event_name = self.registration.event.name
            event_type_id = self.registration.event.type_id

            email_variables = {
                "event": event_name,
                "event_type_id": event_type_id,
                "linked_events_ui_locale": linked_events_ui_locale,
                "linked_events_ui_url": settings.LINKED_EVENTS_UI_URL,
                "linked_registrations_ui_locale": linked_registrations_ui_locale,
                "linked_registrations_ui_url": settings.LINKED_REGISTRATIONS_UI_URL,
                "registration_id": self.registration.id,
                "signup_id": self.id,
                "username": self.first_name,
            }

            confirmation_message = self.registration.confirmation_message
            instructions = self.registration.instructions

        if confirmation_message:
            email_variables["confirmation_message"] = confirmation_message

        if instructions:
            email_variables["instructions"] = instructions

        notification_templates = {
            SignUpNotificationType.CANCELLATION: "cancellation_confirmation.html",
            SignUpNotificationType.CONFIRMATION: "signup_confirmation.html",
            SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST: "signup_confirmation_to_waiting_list.html",
            SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT: "signup_transferred_as_participant.html",
        }

        with override(linked_registrations_ui_locale, deactivate=True):
            event_type_id = self.registration.event.type_id
            notification_subjects = {
                SignUpNotificationType.CANCELLATION: _(
                    "Registration cancelled - %(event_name)s"
                )
                % {"event_name": event_name},
                SignUpNotificationType.CONFIRMATION: _(
                    "Registration confirmation - %(event_name)s"
                )
                % {"event_name": event_name},
                SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST: _(
                    "Waiting list seat reserved - %(event_name)s"
                )
                % {"event_name": self.registration.event.name},
                SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT: _(
                    "Registration confirmation - %(event_name)s"
                )
                % {"event_name": event_name},
            }

            rendered_body = render_to_string(
                notification_templates[notification_type], email_variables
            )

        try:
            send_mail(
                notification_subjects[notification_type],
                rendered_body,
                get_email_noreply_address(),
                [self.email],
                html_message=rendered_body,
            )
        except SMTPException:
            pass


class SeatReservationCode(models.Model):
    seats = models.PositiveSmallIntegerField(
        verbose_name=_("Number of seats"), blank=False, default=0
    )
    registration = models.ForeignKey(
        Registration, on_delete=models.CASCADE, null=False, related_name="reservations"
    )
    code = models.UUIDField(
        verbose_name=_("Seat reservation code"), default=uuid4, editable=False
    )
    timestamp = models.DateTimeField(
        verbose_name=_("Timestamp"), auto_now_add=True, blank=True
    )

    @property
    def expiration(self):
        return self.timestamp + timedelta(minutes=code_validity_duration(self.seats))
