# -*- coding: utf-8 -*-
"""
Models are modeled after schema.org.

When model is going to be serialized as JSON(-LD), model name must be same as
Schema.org schema name, the model name is automatically published in @type
JSON-LD field.
Note: jsonld_type attribute value can be used to override @type definition in
rendering phase.

Schema definitions: http://schema.org/<ModelName>
(e.g. http://schema.org/Event)

Some models have custom fields not found from schema.org. Decide if there's a
need for custom extension types (e.g. Event/MyCustomEvent) as schema.org
documentation is suggesting: http://schema.org/docs/extension.html. Override
schema_org_type can be used to define custom types. Override jsonld_context
attribute to change @context when need to define schemas for custom fields.
"""
import datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.generic import GenericForeignKey
import pytz
from django.contrib.gis.db import models
import reversion
from django_hstore import hstore
from django.utils.translation import ugettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
from django.contrib.contenttypes.models import ContentType
from events import translation_utils
from django.utils.encoding import python_2_unicode_compatible


class SchemalessFieldMixin(models.Model):
    # Custom field not from schema.org
    custom_data = hstore.DictionaryField(null=True, blank=True)
    hstore_objects = hstore.HStoreManager()

    class Meta:
        abstract = True


@python_2_unicode_compatible
class DataSource(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(verbose_name=_('Name'), max_length=255)

    def __str__(self):
        return self.id


class SimpleValueMixin(object):
    """
    Used for models which are simple one-to-many fields
    and can be compared by value when importing as part
    of their related object. These models have no existence
    outside their related object.
    """
    def value_fields(self):
        return []

    def simple_value(self):
        field_names = translation_utils.expand_model_fields(self, self.value_fields())
        return tuple((f, getattr(self, f)) for f in field_names)

    def value_equals(self, other):
        return self.simple_value() == other.simple_value()


@python_2_unicode_compatible
class BaseModel(models.Model):
    id = models.CharField(max_length=50, primary_key=True)
    data_source = models.ForeignKey(DataSource, db_index=True)

    # Properties from schema.org/Thing
    name = models.CharField(verbose_name=_('Name'), max_length=255, db_index=True)
    image = models.URLField(verbose_name=_('Image URL'), null=True, blank=True)

    origin_id = models.CharField(verbose_name=_('Origin ID'), max_length=50, db_index=True, null=True,
                                 blank=True)

    created_time = models.DateTimeField(null=True, blank=True)
    last_modified_time = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User, null=True, blank=True,
        related_name="%(app_label)s_%(class)s_created_by")
    last_modified_by = models.ForeignKey(
        User, null=True, blank=True,
        related_name="%(app_label)s_%(class)s_modified_by")

    @staticmethod
    def now():
        return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

    def __str__(self):
        return self.name

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.id and not self.created_time:
            self.created_time = BaseModel.now()
        self.last_modified_time = BaseModel.now()
        super(BaseModel, self).save(*args, **kwargs)


class Organization(BaseModel):
    pass


class Language(models.Model):
    id = models.CharField(max_length=6, primary_key=True)
    name = models.CharField(verbose_name=_('Name'), max_length=20)

    class Meta:
        verbose_name = _('language')
        verbose_name_plural = _('languages')


class KeywordLabel(models.Model):
    name = models.CharField(verbose_name=_('Name'), max_length=255, db_index=True)
    language = models.ForeignKey(Language, blank=False, null=False)

    class Meta:
        unique_together = (('name', 'language'),)


class Keyword(BaseModel):
    alt_labels = models.ManyToManyField(KeywordLabel, blank=True, related_name='keywords')
    aggregate = models.BooleanField(default=False)
    objects = models.Manager()

    schema_org_type = "Thing/LinkedEventKeyword"

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('keyword')
        verbose_name_plural = _('keywords')


class Place(MPTTModel, BaseModel, SchemalessFieldMixin):
    publisher = models.ForeignKey(Organization, verbose_name=_('Publisher'), db_index=True)
    info_url = models.URLField(verbose_name=_('Place home page'), null=True)
    description = models.TextField(verbose_name=_('Description'), null=True, blank=True)
    parent = TreeForeignKey('self', null=True, blank=True,
                            related_name='children')

    position = models.PointField(srid=settings.PROJECTION_SRID, null=True,
                                 blank=True)

    email = models.EmailField(verbose_name=_('E-mail'), null=True, blank=True)
    telephone = models.CharField(verbose_name=_('Telephone'), max_length=128, null=True, blank=True)
    contact_type = models.CharField(verbose_name=_('Contact type'), max_length=255, null=True, blank=True)
    street_address = models.CharField(verbose_name=_('Street address'), max_length=255, null=True, blank=True)
    address_locality = models.CharField(verbose_name=_('Address locality'), max_length=255, null=True, blank=True)
    address_region = models.CharField(verbose_name=_('Address region'), max_length=255, null=True, blank=True)
    postal_code = models.CharField(verbose_name=_('Postal code'), max_length=128, null=True, blank=True)
    post_office_box_num = models.CharField(verbose_name=_('PO BOX'), max_length=128, null=True,
                                           blank=True)
    address_country = models.CharField(verbose_name=_('Country'), max_length=2, null=True, blank=True)

    deleted = models.BooleanField(verbose_name=_('Deleted'), default=False)

    geo_objects = models.GeoManager()

    class Meta:
        verbose_name = _('place')
        verbose_name_plural = _('places')
        unique_together = (('data_source', 'origin_id'),)

    def __unicode__(self):
        values = filter(lambda x: x, [
            self.street_address, self.postal_code, self.address_locality
        ])
        return u', '.join(values)

reversion.register(Place)


class OpeningHoursSpecification(models.Model):
    GR_BASE_URL = "http://purl.org/goodrelations/v1#"
    WEEK_DAYS = (
        (1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"),
        (5, "Friday"), (6, "Saturday"), (7, "Sunday"), (8, "PublicHolidays")
    )

    place = models.ForeignKey(Place, db_index=True,
                              related_name='opening_hours')
    opens = models.TimeField(null=True, blank=True)
    closes = models.TimeField(null=True, blank=True)
    days_of_week = models.SmallIntegerField(choices=WEEK_DAYS, null=True,
                                            blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_through = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _('opening hour specification')
        verbose_name_plural = _('opening hour specifications')


class Event(MPTTModel, BaseModel, SchemalessFieldMixin):
    jsonld_type = "Event/LinkedEvent"

    """
    eventStatus enumeration is based on http://schema.org/EventStatusType
    """
    SCHEDULED = 1
    CANCELLED = 2
    POSTPONED = 3
    RESCHEDULED = 4

    STATUSES = (
        (SCHEDULED, "EventScheduled"),
        (CANCELLED, "EventCancelled"),
        (POSTPONED, "EventPostponed"),
        (RESCHEDULED, "EventRescheduled"),
    )

    # Properties from schema.org/Thing
    info_url = models.URLField(verbose_name=_('Event home page'), blank=True)
    description = models.TextField(verbose_name=_('Description'), blank=True)
    short_description = models.TextField(verbose_name=_('Short description'), blank=True)

    # Properties from schema.org/CreativeWork
    date_published = models.DateTimeField(verbose_name=_('Date published'), null=True, blank=True)
    # headline and secondary_headline are for cases where
    # the original event data contains a title and a subtitle - in that
    # case the name field is combined from these.
    #
    # secondary_headline is mapped to schema.org alternative_headline
    # and is used for subtitles, that is for
    # secondary, complementary headlines, not "alternative" headlines
    headline = models.CharField(verbose_name=_('Headline'), max_length=255, null=True, db_index=True)
    secondary_headline = models.CharField(verbose_name=_('Secondary headline'), max_length=255, null=True, db_index=True)
    provider = models.CharField(verbose_name=_('Provider'), max_length=512, null=True)
    publisher = models.ForeignKey(Organization, verbose_name=_('Publisher'), db_index=True, related_name='published_events')

    # Properties from schema.org/Event
    event_status = models.SmallIntegerField(verbose_name=_('Event status'), choices=STATUSES,
                                            default=SCHEDULED)
    location = models.ForeignKey(Place, null=True, blank=True)
    location_extra_info = models.CharField(verbose_name=_('Location extra info'), max_length=400, null=True, blank=True)

    start_time = models.DateTimeField(verbose_name=_('Start time'), null=True, db_index=True, blank=True)
    end_time = models.DateTimeField(verbose_name=_('End time'), null=True, db_index=True, blank=True)
    has_start_time = models.BooleanField(default=True)
    has_end_time = models.BooleanField(default=True)

    super_event = TreeForeignKey('self', null=True, blank=True,
                                 related_name='sub_events')

    is_recurring_super = models.BooleanField(default=False)

    # Custom fields not from schema.org
    keywords = models.ManyToManyField(Keyword, null=True, blank=True)
    audience = models.CharField(verbose_name=_('Audience'), max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = _('event')
        verbose_name_plural = _('events')

    class MPTTMeta:
        parent_attr = 'super_event'

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_time = BaseModel.now()
        self.last_modified_time = BaseModel.now()
        super(Event, self).save(*args, **kwargs)

    def __str__(self):
        name = ''
        for lang in settings.LANGUAGES:
            s = getattr(self, 'name_%s' % lang[0], None)
            if s:
                name = s
                break
        val = [name, '(%s)' % self.id]
        dcount = self.get_descendant_count()
        if dcount > 0:
            val.append(u" (%d children)" % dcount)
        else:
            val.append(str(self.start_time))
        return u" ".join(val)

reversion.register(Event)


class Offer(models.Model, SimpleValueMixin):
    event = models.ForeignKey(Event, db_index=True, related_name='offers')
    price = models.CharField(verbose_name=_('Price'), blank=True, max_length=512)
    info_url = models.URLField(verbose_name=_('Web link to offer'), blank=True)
    description = models.TextField(verbose_name=_('Description'), blank=True)
    # Don't expose is_free as an API field. It is used to distinguish
    # between missing price info and confirmed free entry.
    is_free = models.BooleanField(verbose_name=_('Is free'), default=False)

    def value_fields(self):
        return ['price', 'info_url', 'description', 'is_free']

reversion.register(Offer)


class EventLink(models.Model, SimpleValueMixin):
    name = models.CharField(verbose_name=_('Name'), max_length=100, blank=True)
    event = models.ForeignKey(Event, db_index=True, related_name='external_links')
    language = models.ForeignKey(Language)
    link = models.URLField()

    class Meta:
        unique_together = (('event', 'language', 'link'),)

    def value_fields(self):
        return ['name', 'language_id', 'link']


class ExportInfo(models.Model):
    target_id = models.CharField(max_length=255, db_index=True, null=True,
                                 blank=True)
    target_system = models.CharField(max_length=255, db_index=True, null=True,
                                     blank=True)
    last_exported_time = models.DateTimeField(null=True, blank=True)

    content_type = models.ForeignKey(ContentType)
    object_id = models.CharField(max_length=50)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = (('target_system', 'content_type', 'object_id'),)

    def save(self, *args, **kwargs):
        self.last_exported_time = BaseModel.now()
        super(ExportInfo, self).save(*args, **kwargs)


class EventAggregate(models.Model):
    super_event = models.OneToOneField(Event, related_name='aggregate', null=True)


class EventAggregateMember(models.Model):
    event_aggregate = models.ForeignKey(EventAggregate, related_name='members')
    event = models.ForeignKey(Event, unique=True)
