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
from django.utils.text import slugify
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
    code = models.CharField(max_length=6)

    class Meta:
        verbose_name = _('language')
        verbose_name_plural = _('languages')


class Person(BaseModel):
    description = models.TextField(blank=True)
    family_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    creator = models.ForeignKey('self', null=True, blank=True,
                                related_name='person_creators')
    editor = models.ForeignKey('self', null=True, blank=True,
                               related_name='person_editors')
    # Custom fields
    member_of = models.ForeignKey('Organization', null=True, blank=True)
    user = models.ForeignKey(User, null=True, blank=True)

    class Meta:
        verbose_name = _('person')
        verbose_name_plural = _('persons')

reversion.register(Person)


class Organization(BaseModel):
    description = models.TextField(blank=True)
    base_IRI = models.CharField(max_length=200, null=True, blank=True)
    compact_IRI_name = models.CharField(max_length=200, null=True, blank=True)
    creator = models.ForeignKey(Person, null=True, blank=True,
                                related_name='organization_creators')
    editor = models.ForeignKey(Person, null=True, blank=True,
                               related_name='organization_editors')

    class Meta:
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')


reversion.register(Organization)

class CategoryLabel(SystemMetaMixin):
    label = models.CharField(max_length=255, null=False, blank=False, db_index=True)

reversion.register(CategoryLabel)

class Category(MPTTModel, BaseModel, SchemalessFieldMixin):
    schema_org_type = "Thing/LinkedEventCategory"

    CATEGORY_TYPES = (
        (0, 'Event'), (1, 'Place'), (2, 'Organization'), (3, 'Person')
    )

    # category ids from: http://finto.fi/ysa/fi/
    url = models.CharField(max_length=255, db_index=True, null=False, blank=False, default='unknown')
    description = models.TextField(blank=True)
    # label: preferred label
    label = models.CharField(max_length=255, null=False, blank=False, default='unknown')
    # labels: preferred label and alternative labels (for lookups)
    labels = models.ManyToManyField(CategoryLabel, blank=True, related_name='categories')
    same_as = models.CharField(max_length=255, null=True, blank=True)
    parent_category = TreeForeignKey('self', null=True, blank=True)
    creator = models.ForeignKey(Person, null=True, blank=True,
                                related_name='category_creators')
    editor = models.ForeignKey(Person, null=True, blank=True,
                               related_name='category_editors')
    category_for = models.SmallIntegerField(
        choices=CATEGORY_TYPES, null=True, blank=True)

    def __str__(self):
        return self.label

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')

    class MPTTMeta:
        parent_attr = 'parent_category'

reversion.register(Category)


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


class Offer(BaseModel):
    available_at_or_from = models.ForeignKey(Place, null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True,
                                blank=True)
    price_currency = models.CharField(max_length=3, null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_through = models.DateTimeField(null=True, blank=True)
    sku = models.CharField(max_length=255, null=True, blank=True)

    limiter = {"model__in": ["organization", "person"]}
    seller_object_id = models.PositiveIntegerField(null=True, blank=True)
    seller_content_type = models.ForeignKey(ContentType,
                                            limit_choices_to=limiter,
                                            null=True, blank=True)
    seller = GenericForeignKey('seller_content_type', 'seller_object_id')

    class Meta:
        verbose_name = _('offer')
        verbose_name_plural = _('offers')

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
    creator = models.ManyToManyField(Person, blank=True,
                                     related_name='event_creators')
    editor = models.ForeignKey(Person, null=True, blank=True,
                               related_name='event_editors')
    date_published = models.DateTimeField(null=True, blank=True)
    # TODO: Person or Organization
    performer = models.ManyToManyField(Person, blank=True)
    publisher = models.ForeignKey(Organization, null=True, blank=True,
                                  related_name='event_publishers')
    provider = models.ForeignKey(Organization, null=True, blank=True,
                                 related_name='event_providers')

    # Properties from schema.org/Event
    event_status = models.SmallIntegerField(choices=STATUSES,
                                            default=SCHEDULED)
    location = models.ForeignKey(Place, null=True, blank=True)
    # Just ONE offer in offers field at schema.org (???)
    offers = models.ForeignKey(Offer, null=True, blank=True)
    previous_start_date = models.DateTimeField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, db_index=True, blank=True)
    end_time = models.DateTimeField(null=True, db_index=True, blank=True)
    super_event = TreeForeignKey('self', null=True, blank=True,
                                 related_name='sub_event')
    typical_age_range = models.CharField(max_length=255, null=True, blank=True)

    # Custom fields not from schema.org
    target_group = models.CharField(max_length=255, null=True, blank=True)
    category = models.ManyToManyField(Category, null=True, blank=True)
    slug = models.SlugField(blank=True)
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
        if not self.slug:
            self.slug = slugify(self.name[:50])
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

contexts.create_context(Event)
contexts.create_context(Organization)
contexts.create_context(Place)
contexts.create_context(Person)
