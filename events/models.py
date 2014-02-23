import datetime
import pytz

from django.db import models
import reversion

class UpdatableModel(models.Model):
    last_modified_time = models.DateTimeField(null=True)
    last_checked_time = models.DateTimeField(null=True)

    def mark_modified(self):
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        self.last_modified_time = now
    def mark_checked(self):
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        self.last_checked_time = now

    class Meta:
        abstract = True


class Language(models.Model):
    code = models.CharField(max_length=6)
    name = models.CharField(max_length=40)

class Organization(models.Model):
    name = models.CharField(max_length=100)
    last_modified_time = models.DateTimeField(null=True)

class EventCategory(models.Model):
    parent = models.ForeignKey('self', null=True, db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(null=True)

class EventLocation(UpdatableModel):
    name = models.CharField(max_length=250)
    description = models.TextField(null=True)

reversion.register(EventLocation)


class Event(UpdatableModel):
    name = models.CharField(max_length=250)
    description = models.TextField(null=True)

    publisher = models.ForeignKey(Organization, db_index=True)
    origin_id = models.CharField(max_length=50, db_index=True)

    location = models.ForeignKey(EventLocation, db_index=True, null=True)
    language = models.ForeignKey(Language, db_index=True, help_text="Set if the event is in a given language")
    image_url = models.URLField(null=True)
    start_time = models.DateTimeField(null=True, db_index=True)
    end_time = models.DateTimeField(null=True, db_index=True)
    duration = models.CharField(max_length=50, null=True)
    publish_time = models.DateTimeField()
    previous_start_date = models.DateTimeField(null=True)
    event_status = models.PositiveSmallIntegerField() # FIXME: integers suck for this, use CharField and choices instead?

    slug = models.SlugField()

    categories = models.ManyToManyField(EventCategory)
    parent = models.ForeignKey('self', db_index=True)

    class Meta:
        unique_together = (('publisher', 'origin_id'),)

reversion.register(Event)
