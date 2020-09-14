from django.contrib.gis.db import models
from django.utils.translation import ugettext_lazy as _

from .extension import CourseExtension


class Course(models.Model):
    event = models.OneToOneField(
        'events.Event', verbose_name=_('event'), on_delete=models.CASCADE, related_name=CourseExtension.related_name,
        primary_key=True
    )
    enrolment_start_time = models.DateTimeField(verbose_name=_('enrolment start time'), null=True, blank=True)
    enrolment_end_time = models.DateTimeField(verbose_name=_('enrolment end time'), null=True, blank=True)
    maximum_attendee_capacity = models.PositiveIntegerField(
        verbose_name=_('maximum attendee capacity'), null=True, blank=True
    )
    minimum_attendee_capacity = models.PositiveIntegerField(
        verbose_name=_('minimum attendee capacity'), null=True, blank=True
    )
    remaining_attendee_capacity = models.PositiveIntegerField(
        verbose_name=_('remaining attendee capacity'), null=True, blank=True
    )

    class Meta:
        ordering = ('event',)
