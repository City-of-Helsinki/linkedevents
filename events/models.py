"""
Models are modeled after schema.org.

When model is going to be serialized as JSON(-LD), model name must be same as Schema.org schema name,
the model name is automatically published in @type JSON-LD field.
Note: schema_org_type attribute value can be used to override @type definition in rendering phase.

Schema definitions: http://schema.org/<ModelName> (e.g. http://schema.org/Event)

TODO:
    Some models have custom fields not found from schema.org. Decide if there's a need for
    custom extension types (e.g. Event/MyCustomEvent) as schema.org documentation is suggesting:
    http://schema.org/docs/extension.html. Override schema_org_type can be used to define custom
    types.
"""
import datetime
import pytz
from django.db import models
import reversion
from django_hstore import hstore
from django.utils.translation import ugettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
from django.utils.text import slugify


class SchemalessFieldMixin(models.Model):
    # Custom field not from schema.org
    custom_fields = hstore.DictionaryField(null=True, blank=True)
    objects = hstore.HStoreManager()

    class Meta:
        abstract = True


class BaseModel(models.Model):
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
    family_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    creator = models.ForeignKey('self', null=True, blank=True, related_name='person_creators')  # TODO: Person or Organization
    editor = models.ForeignKey('self', null=True, blank=True, related_name='person_editors')  # TODO: Person or Organization
    # Custom fields
    username = models.CharField(max_length=255, null=True, blank=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    member_of = models.ForeignKey('Organization', null=True, blank=True)
    role = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = _('Person')


class Organization(BaseModel):
    description = models.TextField(null=True, blank=True)
    base_IRI = models.CharField(max_length=200, null=True, blank=True)
    compact_IRI_name = models.CharField(max_length=200, null=True, blank=True)
    creator = models.ForeignKey(Person, null=True, blank=True, related_name='organization_creators')  # TODO: Person or Organization
    editor = models.ForeignKey(Person, null=True, blank=True, related_name='organization_editors')  # TODO: Person or Organization

    class Meta:
        verbose_name = _('Organization')

reversion.register(Organization)


class Category(MPTTModel, BaseModel, SchemalessFieldMixin):
    # category ids from: http://finto.fi/ysa/fi/
    description = models.TextField(null=True, blank=True)
    # dynamically created?
    # category_for = models.CharField(max_length=255, null=True, blank=True)
    same_as = models.CharField(max_length=255, null=True, blank=True)
    parent_category = TreeForeignKey('self', null=True, blank=True)
    creator = models.ForeignKey(Person, null=True, blank=True, related_name='category_creators')  # TODO: Person or Organization
    editor = models.ForeignKey(Person, null=True, blank=True, related_name='category_editors')  # TODO: Person or Organization

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
    available_language = models.ForeignKey(Language, db_index=True)


class Place(BaseModel, SchemalessFieldMixin):
    same_as = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True)
    address = models.ForeignKey(PostalAddress, null=True, blank=True)
    publishing_principles = models.CharField(max_length=255, null=True, blank=True)
    elevation = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    point = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    logo = models.CharField(max_length=255, null=True, blank=True)
    map = models.CharField(max_length=255, null=True, blank=True)
    #contained_in = TreeForeignKey('self', null=True, blank=True, related_name='children')
    creator = models.ForeignKey(Person, null=True, blank=True, related_name='place_creators')  # TODO: Person or Organization
    editor = models.ForeignKey(Person, null=True, blank=True, related_name='place_editors')  # TODO: Person or Organization

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

    place = models.OneToOneField(Place, primary_key=True)
    opens = models.TimeField(null=True, blank=True)
    closes = models.TimeField(null=True, blank=True)
    days_of_week = models.SmallIntegerField(choices=WEEK_DAYS, null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_through = models.DateTimeField(null=True, blank=True)


class GeoShape(models.Model):
    place = models.OneToOneField(Place, primary_key=True)
    elevation = models.CharField(max_length=255, null=True, blank=True)
    box = models.CharField(max_length=255, null=True, blank=True)
    circle = models.CharField(max_length=255, null=True, blank=True)
    line = models.CharField(max_length=255, null=True, blank=True)
    polygon = models.TextField(null=True, blank=True)


class GeoCoordinates(models.Model):
    place = models.OneToOneField(Place, primary_key=True)
    elevation = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.CharField(max_length=255, null=True, blank=True)
    longitude = models.CharField(max_length=255, null=True, blank=True)


class Offer(BaseModel):
    #available_at_or_from = models.ForeignKey(Place, null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    price_currency = models.CharField(max_length=3, null=True, blank=True)
    seller = models.CharField(max_length=255, null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_through = models.DateTimeField(null=True, blank=True)
    sku = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = _('Offer')


class Event(MPTTModel, BaseModel, SchemalessFieldMixin):

    schema_org_type = "Event/LinkedEvent"

    """
    Status enumeration is based on http://schema.org/EventStatusType
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
    same_as = models.CharField(max_length=255, null=True, blank=True, unique=True)
    description = models.TextField(null=True)

    # Properties from schema.org/CreativeWork
    creator = models.ForeignKey(Person, null=True, blank=True, related_name='event_creators')  # TODO: Person or Organization
    editor = models.ForeignKey(Person, null=True, blank=True, related_name='event_editors')  # TODO: Person or Organization

    # Properties from schema.org/Event
    door_time = models.TimeField(null=True, blank=True)
    duration = models.CharField(max_length=50, null=True, blank=True)
    end_date = models.DateField(null=True, db_index=True, blank=True)
    event_status = models.SmallIntegerField(choices=STATUSES, default=SCHEDULED)
    location = models.ForeignKey(Place, null=True, blank=True)
    offers = models.ManyToManyField(Offer, blank=True)
    previous_start_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, db_index=True, blank=True)
    super_event = TreeForeignKey('self', null=True, blank=True, related_name='children')
    typical_age_range = models.CharField(max_length=255, null=True, blank=True)

    # Properties from schema.org/CreativeWork
    date_published = models.DateTimeField()
    performer = models.ForeignKey(Person, null=True, blank=True)  # TODO: Person or Organization
    publisher = models.ForeignKey(Organization, null=True, blank=True)

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
            self.slug = slugify(self.name)
        #self.mark_checked()
        self.last_modified_time = BaseModel.now()
        super(Event, self).save(*args, **kwargs)

reversion.register(Event)
