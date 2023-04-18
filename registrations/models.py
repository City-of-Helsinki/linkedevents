from smtplib import SMTPException
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.db import models
from django.forms.fields import MultipleChoiceField
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from events.models import Event, Language

User = settings.AUTH_USER_MODEL


class MandatoryFields(models.TextChoices):
    """Choices for mandatory fields on SignUp model."""

    CITY = "city", _("City")
    NAME = "name", _("Name")
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


class Registration(models.Model):
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

    created_at = models.DateTimeField(verbose_name=_("Created at"), auto_now_add=True)
    last_modified_at = models.DateTimeField(
        verbose_name=_("Modified at"), null=True, blank=True, auto_now=True
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registration_created_by",
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registration_last_modified_by",
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

    def can_be_edited_by(self, user):
        """Check if current registration can be edited by the given user"""
        if user.is_superuser:
            return True
        return user.is_admin(self.event.publisher)

    def is_user_editable_resources(self):
        return bool(
            self.event.data_source and self.event.data_source.user_editable_resources
        )


class SignUp(models.Model):
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

    registration = models.ForeignKey(
        Registration, on_delete=models.CASCADE, related_name="signups"
    )
    name = models.CharField(
        verbose_name=_("Name"),
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
    cancellation_code = models.UUIDField(
        verbose_name=_("Cancellation code"), default=uuid4, editable=False
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

    class Meta:
        unique_together = [["email", "registration"], ["phone_number", "registration"]]

    def send_notification(self, confirmation_type):
        email_variables = {
            "linked_events_ui_url": settings.LINKED_EVENTS_UI_URL,
            "linked_registrations_ui_url": settings.LINKED_REGISTRATIONS_UI_URL,
            "username": self.name,
            "event": self.registration.event.name_fi,
            "cancellation_code": self.cancellation_code,
            "registration_id": self.registration.id,
        }

        if self.registration.confirmation_message:
            email_variables[
                "confirmation_message"
            ] = self.registration.confirmation_message

        if self.registration.instructions:
            email_variables["instructions"] = self.registration.instructions

        event_type_name = {
            str(Event.TypeId.GENERAL): _("tapahtumaan"),
            str(Event.TypeId.COURSE): _("kurssille"),
            str(Event.TypeId.VOLUNTEERING): _("vapaaehtoistehtävään"),
        }

        email_variables["event_type"] = event_type_name[self.registration.event.type_id]

        confirmation_types = {
            "confirmation": "signup_confirmation.html",
            "cancellation": "cancellation_confirmation.html",
        }
        rendered_body = render_to_string(
            confirmation_types[confirmation_type], email_variables
        )

        confirmation_subjects = {
            "confirmation": _("Vahvistus ilmoittautumisesta - %(event_name)s")
            % {"event_name": self.registration.event.name},
            "cancellation": _("Ilmoittautuminen peruttu - %(event_name)s")
            % {"event_name": self.registration.event.name},
        }

        try:
            send_mail(
                confirmation_subjects[confirmation_type],
                rendered_body,
                f"letest@{Site.objects.get_current().domain}",
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
