from uuid import uuid4
from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from events.models import Event

User = settings.AUTH_USER_MODEL


class Registration(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='registration', null=False)
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
    class NotificationType:
        NO_NOTIFICATION = 0
        SMS = 1
        EMAIL = 2
        SMS_EMAIL = 3

    NOTIFICATION_TYPES = (
        (NotificationType.NO_NOTIFICATION, _("No Notification")),
        (NotificationType.SMS, _("SMS")),
        (NotificationType.EMAIL, _("E-Mail")),
        (NotificationType.SMS_EMAIL, _("Both SMS and email."))
        )

    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='signups')
    name = models.CharField(max_length=50)
    city = models.CharField(max_length=50, blank=True, default='')
    email = models.EmailField()
    extra_info = models.TextField(blank=True, default='')
    membership_number = models.CharField(max_length=50, blank=True, default='')
    phone_number = models.CharField(max_length=18, blank=True, default='')
    notifications = models.PositiveSmallIntegerField(verbose_name=_("Notification type"), choices=NOTIFICATION_TYPES,
                                                     default=NotificationType.NO_NOTIFICATION)
    cancellation_code = models.UUIDField(default=uuid4, editable=False)

    class Meta:
        unique_together = [['email', 'registration'], ['phone_number', 'registration']]
