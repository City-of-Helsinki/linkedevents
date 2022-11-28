import pytz
from uuid import uuid4
from datetime import datetime
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from events.models import Event, Language
from django.template.loader import render_to_string
from django.core.mail import send_mail
from smtplib import SMTPException
from django.contrib.sites.models import Site

User = settings.AUTH_USER_MODEL


class Registration(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='registration', null=False, blank=True)
    attendee_registration = models.BooleanField(default=False, null=False)
    audience_min_age = models.PositiveSmallIntegerField(verbose_name=_('Minimum recommended age'),
                                                        blank=True, null=True, db_index=True)
    audience_max_age = models.PositiveSmallIntegerField(verbose_name=_('Maximum recommended age'),
                                                        blank=True, null=True, db_index=True)

    created_at = models.DateTimeField(verbose_name=_('Created at'), auto_now_add=True)
    last_modified_at = models.DateTimeField(verbose_name=_('Modified at'), null=True, blank=True, auto_now=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="registration_created_by")
    last_modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="registration_last_modified_by")

    enrolment_start_time = models.DateTimeField(verbose_name=_('Enrollment start time'), blank=True, null=True)
    enrolment_end_time = models.DateTimeField(verbose_name=_('Enrollment end time'), blank=True, null=True)

    confirmation_message = models.TextField(verbose_name=_('Confirmation message'), blank=True, null=True)
    instructions = models.TextField(verbose_name=_('Instructions'), blank=True, null=True)

    maximum_attendee_capacity = models.PositiveSmallIntegerField(verbose_name=_('Maximum attendee capacity'),
                                                                 null=True, blank=True)
    minimum_attendee_capacity = models.PositiveSmallIntegerField(verbose_name=_('Minimum attendee capacity'),
                                                                 null=True, blank=True)
    waiting_list_capacity = models.PositiveSmallIntegerField(verbose_name=_('Minimum attendee capacity'),
                                                             null=True, blank=True)


class SignUp(models.Model):
    class AttendeeStatus:
        WAITING_LIST = 'waitlisted'
        ATTENDING = 'attending'

    ATTENDEE_STATUSES = ((AttendeeStatus.WAITING_LIST, _("Waitlisted")),
                         (AttendeeStatus.ATTENDING, _("Attending")))

    class NotificationType:
        NO_NOTIFICATION = 'none'
        SMS = 'sms'
        EMAIL = 'email'
        SMS_EMAIL = 'sms and email'

    NOTIFICATION_TYPES = ((NotificationType.NO_NOTIFICATION, _("No Notification")),
                          (NotificationType.SMS, _("SMS")),
                          (NotificationType.EMAIL, _("E-Mail")),
                          (NotificationType.SMS_EMAIL, _("Both SMS and email.")))

    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='signups')
    name = models.CharField(verbose_name=_('Name'), max_length=50)
    date_of_birth = models.DateField(verbose_name=_('Date of birth'), blank=True, null=True)
    city = models.CharField(verbose_name=_('City'), max_length=50, blank=True, default='')
    email = models.EmailField(verbose_name=_('E-mail'), blank=True, null=True, default=None)
    extra_info = models.TextField(verbose_name=_('Extra info'), blank=True, default='')
    membership_number = models.CharField(verbose_name=_('Membership number'), max_length=50, blank=True, default='')
    phone_number = models.CharField(verbose_name=_('Phone number'), max_length=18, blank=True, null=True, default=None)
    notifications = models.CharField(verbose_name=_('Notification type'), max_length=25, choices=NOTIFICATION_TYPES,
                                     default=NotificationType.NO_NOTIFICATION)
    cancellation_code = models.UUIDField(verbose_name=_('Cancellation code'), default=uuid4, editable=False)
    attendee_status = models.CharField(verbose_name=_('Attendee status'), max_length=25, choices=ATTENDEE_STATUSES,
                                       default=AttendeeStatus.ATTENDING)
    native_language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="signup_native_language")
    service_language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="signup_service_language")
    street_address = models.CharField(verbose_name=_('Street address'),
                                      max_length=500, blank=True, null=True, default=None)
    zipcode = models.CharField(verbose_name=_('Street address'), max_length=10, blank=True, null=True, default=None)

    class Meta:
        unique_together = [['email', 'registration'], ['phone_number', 'registration']]

    def send_notification(self, confirmation_type):
        email_variables = {'username': self.name,
                           'event': self.registration.event.name_fi,
                           'cancellation_code': self.cancellation_code,
                           'registration_id': self.registration.id}

        if self.registration.confirmation_message:
            email_variables['confirmation_message'] = self.registration.confirmation_message

        if self.registration.instructions:
            email_variables['instructions'] = self.registration.instructions

        event_type_name = {str(Event.Type_Id.GENERAL): 'tapahtumaan',
                           str(Event.Type_Id.COURSE): 'kurssille',
                           str(Event.Type_Id.VOLUNTEERING): 'vapaaehtoistehtävään'}

        email_variables['event_type'] = event_type_name[self.registration.event.type_id]

        confirmation_types = {'confirmation': 'signup_confirmation.html',
                              'cancellation': 'cancellation_confirmation.html'}
        rendered_body = render_to_string(confirmation_types[confirmation_type], email_variables)

        try:
            send_mail(
                f'{self.registration.event.name} ilmoittautuminen onnistuu!',
                rendered_body,
                f'letest@{Site.objects.get_current().domain}',
                [self.email],
                html_message=rendered_body
            )
        except SMTPException:
            pass


class SeatReservationCode(models.Model):
    seats = models.PositiveSmallIntegerField(verbose_name=_('Number of seats'), blank=False, default=0)
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, null=False, related_name='reservations')
    code = models.UUIDField(verbose_name=_('Seat reservation code'), default=uuid4, editable=False)
    timestamp = models.DateTimeField(verbose_name=_('Timestamp.'), auto_now_add=True, blank=True)
