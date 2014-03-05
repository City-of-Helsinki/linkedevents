import datetime
import pytz
from django.db import models
import reversion
from django_hstore import hstore
from django.utils.translation import ugettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
from django.utils.text import slugify


class BaseModel(models.Model):
    name = models.CharField(max_length=255)
    date_created = models.DateTimeField(null=True, blank=True)
    date_modified = models.DateTimeField(null=True, blank=True)
    creator = models.CharField(max_length=255, null=True, blank=True)
    editor = models.CharField(max_length=255, null=True, blank=True)

    @staticmethod
    def now():
        return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

    def __unicode__(self):
        return self.name

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_time = BaseModel.now()
        self.last_modified_time = BaseModel.now()
        super(BaseModel, self).save(*args, **kwargs)


class Language(BaseModel):
    code = models.CharField(max_length=6)

    class Meta:
        verbose_name = _('Language')


class Organization(BaseModel):
    description = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = _('Organization')

reversion.register(Organization)


class EventCategory(MPTTModel, BaseModel):
    parent = TreeForeignKey('self', null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = _('Category')

reversion.register(EventCategory)


class EventLocation(BaseModel):
    description = models.TextField(null=True)

    class Meta:
        verbose_name = _('Location')

reversion.register(EventLocation)


class Event(MPTTModel, BaseModel):
    # based on schema.org EventStatusType
    SCHEDULED = "EventScheduled"
    CANCELLED = "EventCancelled"
    POSTPONED = "EventPostponed"
    RESCHEDULED = "EventRescheduled"

    STATUSES = (
        (SCHEDULED, SCHEDULED),
        (CANCELLED, CANCELLED),
        (POSTPONED, POSTPONED),
        (RESCHEDULED, RESCHEDULED),
    )

    description = models.TextField(null=True)
    publisher = models.ForeignKey(Organization, db_index=True)
    origin_id = models.CharField(max_length=50, db_index=True)
    location = models.ForeignKey(EventLocation, db_index=True, null=True)
    language = models.ForeignKey(Language, db_index=True, help_text=_("Set if the event is in a given language"))
    image = models.URLField(null=True, blank=True)
    start_date = models.DateField(null=True, db_index=True, blank=True)
    end_date = models.DateField(null=True, db_index=True, blank=True)
    duration = models.CharField(max_length=50, null=True, blank=True)
    date_published = models.DateTimeField()
    previous_start_date = models.DateTimeField(null=True, blank=True)
    event_status = models.CharField(choices=STATUSES, max_length=50, default=SCHEDULED)
    typical_age_range = models.CharField(max_length=250, null=True, blank=True)
    slug = models.SlugField(blank=True)
    categories = models.ManyToManyField(EventCategory)
    super_event = TreeForeignKey('self', null=True, blank=True, related_name='children')
    custom_fields = hstore.DictionaryField(null=True, blank=True)
    objects = hstore.HStoreManager()

    class Meta:
        unique_together = (('publisher', 'origin_id'),)
        verbose_name = _('Event')

    class MPTTMeta:
        parent_attr = 'super_event'

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_time = BaseModel.now()
        if not self.slug:
            self.slug = slugify(self.name)
        #self.mark_checked()
        self.last_modified_time = BaseModel.now()
        super(Event, self).save(*args, **kwargs)

reversion.register(Event)
