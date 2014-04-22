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
from events import contexts
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class DataSource(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=255)
    event_url_template = models.CharField(max_length=200, null=True)

    def event_same_as(self, origin_id):
        if origin_id is not None:
            return self.event_url_template.format(origin_id=origin_id)
        else:
            return None

    def __str__(self):
        return self.id


class SystemMetaMixin(models.Model):
    created_by = models.ForeignKey(
        User, null=True, blank=True,
        related_name="%(app_label)s_%(class)s_created_by")
    modified_by = models.ForeignKey(
        User, null=True, blank=True,
        related_name="%(app_label)s_%(class)s_modified_by")
    data_source = models.ForeignKey(DataSource, db_index=True, null=True,
                                    blank=True)
    origin_id = models.CharField(max_length=255, db_index=True, null=True,
                                 blank=True)

    class Meta:
        abstract = True


class SchemalessFieldMixin(models.Model):
    # Custom field not from schema.org
    custom_fields = hstore.DictionaryField(null=True, blank=True)
    hstore_objects = hstore.HStoreManager()

    class Meta:
        abstract = True


@python_2_unicode_compatible
class BaseModel(SystemMetaMixin):
    # Properties from schema.org/Thing
    name = models.CharField(max_length=255, db_index=True)
    image = models.URLField(null=True, blank=True)

    created_time = models.DateTimeField(null=True, blank=True)
    last_modified_time = models.DateTimeField(null=True, blank=True)

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


class Language(BaseModel):
    id = models.CharField(max_length=6, primary_key=True)

    class Meta:
        verbose_name = _('language')
        verbose_name_plural = _('languages')


class CategoryLabel(BaseModel):
    language = models.ForeignKey(Language, blank=False, null=False)

    class Meta:
        unique_together = (('name', 'language'),)


class Category(BaseModel, SchemalessFieldMixin):
    objects = models.Manager()

    schema_org_type = "Thing/LinkedEventCategory"

    CATEGORY_TYPES = (
        (0, 'Event'), (1, 'Place'),
    )

    # category ids from: http://finto.fi/ysa/fi/
    url = models.CharField(max_length=255, db_index=True, null=False, blank=False, default='unknown')
    description = models.TextField(blank=True)
    alt_labels = models.ManyToManyField(CategoryLabel, blank=True, related_name='categories')
    same_as = models.CharField(max_length=255, null=True, blank=True)
    aggregate = models.BooleanField(default=False)
    category_for = models.SmallIntegerField(
        choices=CATEGORY_TYPES, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')


class Place(MPTTModel, BaseModel, SchemalessFieldMixin):
    same_as = models.CharField(max_length=255, db_index=True, null=True,
                               blank=True)
    description = models.TextField(null=True, blank=True)
    parent = TreeForeignKey('self', null=True, blank=True,
                            related_name='children')

    location = models.PointField(srid=settings.PROJECTION_SRID, null=True,
                                 blank=True)

    email = models.EmailField(null=True, blank=True)
    telephone = models.CharField(max_length=128, null=True, blank=True)
    contact_type = models.CharField(max_length=255, null=True, blank=True)
    street_address = models.CharField(max_length=255, null=True, blank=True)
    address_locality = models.CharField(max_length=255, null=True, blank=True)
    address_region = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=128, null=True, blank=True)
    post_office_box_num = models.CharField(max_length=128, null=True,
                                           blank=True)
    address_country = models.CharField(max_length=2, null=True, blank=True)

    deleted = models.BooleanField(default=False)

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

    place = models.OneToOneField(Place, primary_key=True,
                                 related_name='opening_hour_specification')
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
    url = models.URLField(_('Event home page'), blank=True)
    description = models.TextField(blank=True)

    # Properties from schema.org/CreativeWork
    date_published = models.DateTimeField(null=True, blank=True)
    # provider = models.ForeignKey(Organization, null=True, blank=True,
    #                             related_name='event_providers')

    # Properties from schema.org/Event
    event_status = models.SmallIntegerField(choices=STATUSES,
                                            default=SCHEDULED)
    location = models.ForeignKey(Place, null=True, blank=True)
    start_time = models.DateTimeField(null=True, db_index=True, blank=True)
    end_time = models.DateTimeField(null=True, db_index=True, blank=True)
    super_event = TreeForeignKey('self', null=True, blank=True,
                                 related_name='sub_event')

    # Custom fields not from schema.org
    target_group = models.CharField(max_length=255, null=True, blank=True)
    categories = models.ManyToManyField(Category, null=True, blank=True)
    language = models.ForeignKey(Language, blank=True, null=True,
                                 help_text=_("Set if the event is in a given "
                                             "language"))

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

    def same_as(self):
        return self.data_source.event_same_as(self.origin_id)

    def __str__(self):
        val = [self.name]
        dcount = self.get_descendant_count()
        if dcount > 0:
            val.append(u" (%d children)" % dcount)
        else:
            val.append(str(self.start_time))
        return u" ".join(val)

reversion.register(Event)


class ExportInfo(models.Model):
    target_id = models.CharField(max_length=255, db_index=True, null=True,
                                 blank=True)
    target_system = models.CharField(max_length=255, db_index=True, null=True,
                                     blank=True)
    last_exported_time = models.DateTimeField(null=True, blank=True)

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = (('target_system', 'content_type', 'object_id'),)

    def save(self, *args, **kwargs):
        self.last_exported_time = BaseModel.now()
        super(ExportInfo, self).save(*args, **kwargs)

contexts.create_context(Event)
contexts.create_context(Place)
