# -*- coding: utf-8 -*-
"""
Models are modeled after schema.org.

When model is going to be serialized as JSON(-LD), model name must be same as Schema.org schema name,
the model name is automatically published in @type JSON-LD field.
Note: jsonld_type attribute value can be used to override @type definition in rendering phase.

Schema definitions: http://schema.org/<ModelName> (e.g. http://schema.org/Event)

Some models have custom fields not found from schema.org. Decide if there's a need for
custom extension types (e.g. Event/MyCustomEvent) as schema.org documentation is suggesting:
http://schema.org/docs/extension.html. Override schema_org_type can be used to define custom
types.
Override jsonld_context attribute to change @context when need to define schemas for custom fields.
"""
import datetime
from django.contrib.auth.models import User
from django.contrib.contenttypes.generic import GenericForeignKey
import pytz
from django.db import models
import reversion
from django_hstore import hstore
from django.utils.translation import ugettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
from django.utils.text import slugify
from django.contrib.contenttypes.models import ContentType
from events import contexts


class DataSource(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=255)
    event_url_template = models.CharField(max_length=200)

    def event_same_as(self, origin_id):
        if origin_id is not None:
            return self.event_url_template.format(origin_id=origin_id)
        else:
            return None

    def __unicode__(self):
        return self.id


class SystemMetaMixin(models.Model):
    created_by = models.ForeignKey(User, null=True, blank=True, related_name="%(app_label)s_%(class)s_created_by")
    modified_by = models.ForeignKey(User, null=True, blank=True, related_name="%(app_label)s_%(class)s_modified_by")
    data_source = models.ForeignKey(DataSource, null=True, blank=True)
    origin_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        abstract = True


class SchemalessFieldMixin(models.Model):
    # Custom field not from schema.org
    custom_fields = hstore.DictionaryField(null=True, blank=True)
    objects = hstore.HStoreManager()

    class Meta:
        abstract = True


class BaseModel(SystemMetaMixin):
    # Properties from schema.org/Thing
    name = models.CharField(max_length=255)
    image = models.URLField(null=True, blank=True)

    # Properties from schema.org/CreativeWork
    date_created = models.DateTimeField(null=True, blank=True)
    date_modified = models.DateTimeField(null=True, blank=True)
    discussion_url = models.URLField(null=True, blank=True)
    thumbnail_url = models.URLField(null=True, blank=True)

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


class Person(BaseModel):
    description = models.TextField(blank=True)
    family_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    creator = models.ForeignKey('self', null=True, blank=True, related_name='person_creators')  # TODO: Person or Organization
    editor = models.ForeignKey('self', null=True, blank=True, related_name='person_editors')  # TODO: Person or Organization
    # Custom fields
    member_of = models.ForeignKey('Organization', null=True, blank=True)
    user = models.ForeignKey(User, null=True, blank=True)

    class Meta:
        verbose_name = _('Person')

reversion.register(Person)


class Organization(BaseModel):
    description = models.TextField(blank=True)
    base_IRI = models.CharField(max_length=200, null=True, blank=True)
    compact_IRI_name = models.CharField(max_length=200, null=True, blank=True)
    creator = models.ForeignKey(Person, null=True, blank=True, related_name='organization_creators')  # TODO: Person or Organization
    editor = models.ForeignKey(Person, null=True, blank=True, related_name='organization_editors')  # TODO: Person or Organization

    class Meta:
        verbose_name = _('Organization')

reversion.register(Organization)


class Category(MPTTModel, BaseModel, SchemalessFieldMixin):
    schema_org_type = "Thing/LinkedEventCategory"

    CATEGORY_TYPES = (
        (0, 'Event'), (1, 'Place'), (2, 'Organization'), (3, 'Person')
    )

    # category ids from: http://finto.fi/ysa/fi/
    description = models.TextField(blank=True)
    same_as = models.CharField(max_length=255, null=True, blank=True)
    parent_category = TreeForeignKey('self', null=True, blank=True)
    creator = models.ForeignKey(Person, null=True, blank=True, related_name='category_creators')  # TODO: Person or Organization
    editor = models.ForeignKey(Person, null=True, blank=True, related_name='category_editors')  # TODO: Person or Organization
    category_for = models.SmallIntegerField(choices=CATEGORY_TYPES, null=True, blank=True)

    class Meta:
        verbose_name = _('Category')

    class MPTTMeta:
        parent_attr = 'parent_category'

reversion.register(Category)


class PostalAddress(BaseModel):
    email = models.EmailField(null=True, blank=True)
    telephone = models.CharField(max_length=128, null=True, blank=True)
    contact_type = models.CharField(max_length=255, null=True, blank=True)
    street_address = models.CharField(max_length=255, null=True, blank=True)
    address_locality = models.CharField(max_length=255, null=True, blank=True)
    address_region = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=128, null=True, blank=True)
    post_office_box_num = models.CharField(max_length=128, null=True, blank=True)
    address_country = models.CharField(max_length=2, null=True, blank=True)
    available_language = models.ForeignKey(Language, null=True, blank=True)

    def __unicode__(self):
        values = filter(lambda x: x, [
            self.street_address, self.postal_code, self.address_locality
        ])
        return u', '.join(values)


class Place(MPTTModel, BaseModel, SchemalessFieldMixin):
    same_as = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(blank=True)
    address = models.ForeignKey(PostalAddress, null=True, blank=True)
    publishing_principles = models.CharField(max_length=255, null=True, blank=True)
    point = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    logo = models.CharField(max_length=255, null=True, blank=True)
    map = models.CharField(max_length=255, null=True, blank=True)
    contained_in = TreeForeignKey('self', null=True, blank=True, related_name='children')
    creator = models.ForeignKey(Person, null=True, blank=True, related_name='place_creators')  # TODO: Person or Organization
    editor = models.ForeignKey(Person, null=True, blank=True, related_name='place_editors')  # TODO: Person or Organization

    def __unicode__(self):
        return u', '.join([self.name, unicode(self.address if self.address else '')])

    class Meta:
        verbose_name = _('Place')

    class MPTTMeta:
        parent_attr = 'contained_in'

reversion.register(Place)


class OpeningHoursSpecification(models.Model):

    GR_BASE_URL = "http://purl.org/goodrelations/v1#"
    WEEK_DAYS = (
        (1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"),
        (5, "Friday"), (6, "Saturday"), (7, "Sunday"), (8, "PublicHolidays")
    )

    place = models.OneToOneField(Place, primary_key=True, related_name='opening_hour_specification')
    opens = models.TimeField(null=True, blank=True)
    closes = models.TimeField(null=True, blank=True)
    days_of_week = models.SmallIntegerField(choices=WEEK_DAYS, null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_through = models.DateTimeField(null=True, blank=True)


class GeoInfo(models.Model):
    GEO_TYPES = (
        (0, "GeoShape"), (1, "GeoCoordinates")
    )

    @property
    def jsonld_type(self):
        return self.GEO_TYPES[self.geo_type][1]

    place = models.OneToOneField(Place, primary_key=True, related_name='geo')
    elevation = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.CharField(max_length=255, null=True, blank=True)
    longitude = models.CharField(max_length=255, null=True, blank=True)
    box = models.CharField(max_length=255, null=True, blank=True)
    circle = models.CharField(max_length=255, null=True, blank=True)
    line = models.CharField(max_length=255, null=True, blank=True)
    polygon = models.TextField(null=True, blank=True)
    geo_type = models.SmallIntegerField(choices=GEO_TYPES, default=GEO_TYPES[0][0])


class Offer(BaseModel):
    available_at_or_from = models.ForeignKey(Place, null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    price_currency = models.CharField(max_length=3, null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_through = models.DateTimeField(null=True, blank=True)
    sku = models.CharField(max_length=255, null=True, blank=True)

    limiter = {"model__in": ["organization", "person"]}
    seller_object_id = models.PositiveIntegerField(null=True, blank=True)
    seller_content_type = models.ForeignKey(ContentType, limit_choices_to=limiter, null=True, blank=True)
    seller = GenericForeignKey('seller_content_type', 'seller_object_id')

    class Meta:
        verbose_name = _('Offer')


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
    creator = models.ManyToManyField(Person, blank=True, related_name='event_creators')  # TODO: Person or Organization
    editor = models.ForeignKey(Person, null=True, blank=True, related_name='event_editors')  # TODO: Person or Organization
    date_published = models.DateTimeField(null=True, blank=True)
    performer = models.ManyToManyField(Person, blank=True)  # TODO: Person or Organization
    publisher = models.ForeignKey(Organization, null=True, blank=True, related_name='event_publishers')
    provider = models.ForeignKey(Organization, null=True, blank=True, related_name='event_providers')

    # Properties from schema.org/Event
    door_time = models.TimeField(null=True, blank=True)
    duration = models.CharField(max_length=50, null=True, blank=True)
    end_date = models.DateField(null=True, db_index=True, blank=True)
    event_status = models.SmallIntegerField(choices=STATUSES, default=SCHEDULED)
    location = models.ForeignKey(Place, null=True, blank=True)
    # Just ONE offer in offers field at schema.org (???)
    offers = models.ForeignKey(Offer, null=True, blank=True)
    previous_start_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, db_index=True, blank=True)
    super_event = TreeForeignKey('self', null=True, blank=True, related_name='sub_event')
    typical_age_range = models.CharField(max_length=255, null=True, blank=True)

    # Custom fields not from schema.org
    target_group = models.CharField(max_length=255, null=True, blank=True)
    category = models.ManyToManyField(Category, null=True, blank=True)
    slug = models.SlugField(blank=True)
    language = models.ForeignKey(Language, blank=True, null=True,
                                 help_text=_("Set if the event is in a given language"))

    class Meta:
        verbose_name = _('Event')

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

    def __unicode__(self):
        val = [self.name]
        dcount = self.get_descendant_count()
        if dcount > 0:
            val.append(u" (%d children)" % dcount)
        else:
            val.append(unicode(self.start_date))
            val.append(unicode(self.door_time))
        return u" ".join(val)

reversion.register(Event)
contexts.create_context(Event)
