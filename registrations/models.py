from uuid import uuid4
from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from events.models import Event

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

    ATTENDEE_STATUSES = (
        (AttendeeStatus.WAITING_LIST, _("Waitlisted")),
        (AttendeeStatus.ATTENDING, _("Attending"))
        )

    class NotificationType:
        NO_NOTIFICATION = 'none'
        SMS = 'sms'
        EMAIL = 'email'
        SMS_EMAIL = 'sms and email'

    NOTIFICATION_TYPES = (
        (NotificationType.NO_NOTIFICATION, _("No Notification")),
        (NotificationType.SMS, _("SMS")),
        (NotificationType.EMAIL, _("E-Mail")),
        (NotificationType.SMS_EMAIL, _("Both SMS and email."))
        )

    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='signups')
    name = models.CharField(verbose_name=_('Name'), max_length=50)
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

    class Meta:
        unique_together = [['email', 'registration'], ['phone_number', 'registration']]
