import datetime
import pytz
from django.db import models
import reversion
from django_hstore import hstore
from django.utils.translation import ugettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
from django.utils.text import slugify


class SchemalessFieldMixin(models.Model):
    custom_fields = hstore.DictionaryField(null=True, blank=True)
    objects = hstore.HStoreManager()

    class Meta:
        abstract = True


class BaseModel(models.Model):
    name = models.CharField(max_length=255)
    date_created = models.DateTimeField(null=True, blank=True)
    date_modified = models.DateTimeField(null=True, blank=True)
    creator = models.CharField(max_length=255, null=True, blank=True)
    editor = models.CharField(max_length=255, null=True, blank=True)
    image = models.URLField(null=True, blank=True)
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


class Organization(BaseModel):
    description = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = _('Organization')

reversion.register(Organization)


class Category(MPTTModel, BaseModel, SchemalessFieldMixin):
    same_as = models.CharField(max_length=255, null=True, blank=True)
    parent_category = TreeForeignKey('self', null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = _('Category')

    class MPTTMeta:
        parent_attr = 'parent_category'

reversion.register(Category)


class PlacePostalAddress(BaseModel):
    email = models.EmailField(null=True, blank=True)
    telephone = models.CharField(max_length=128, null=True, blank=True)
    contact_type = models.CharField(max_length=255, null=True, blank=True)
    street_address = models.CharField(max_length=255, null=True, blank=True)
    address_locality = models.CharField(max_length=255, null=True, blank=True)
    address_region = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=128, null=True, blank=True)
    post_office_box_num = models.CharField(max_length=128, null=True, blank=True)
    address_country = models.CharField(max_length=2, null=True, blank=True)
    availableLanguage = models.ForeignKey(Language, db_index=True)


class Place(BaseModel, SchemalessFieldMixin):
    same_as = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True)
    address = models.ForeignKey(PlacePostalAddress, null=True, blank=True)
    publishing_principles = models.CharField(max_length=255, null=True, blank=True)
    elevation = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    point = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    logo = models.CharField(max_length=255, null=True, blank=True)
    map = models.CharField(max_length=255, null=True, blank=True)
    contained_in = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = _('Place')

reversion.register(Place)


class Offer(BaseModel):
    available_at_or_from = models.CharField(max_length=255, null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    price_currency = models.CharField(max_length=3, null=True, blank=True)
    seller = models.CharField(max_length=255, null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_through = models.DateTimeField(null=True, blank=True)
    sku = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = _('Offer')


class Event(MPTTModel, BaseModel, SchemalessFieldMixin):

    # based on schema.org EventStatusType
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

    same_as = models.CharField(max_length=255, null=True, blank=True, unique=True)
    description = models.TextField(null=True)
    publisher = models.ForeignKey(Organization, null=True, blank=True)
    location = models.ForeignKey(Place, null=True, blank=True)
    language = models.ForeignKey(Language, blank=True, null=True,
                                 help_text=_("Set if the event is in a given language"))
    start_date = models.DateField(null=True, db_index=True, blank=True)
    end_date = models.DateField(null=True, db_index=True, blank=True)
    duration = models.CharField(max_length=50, null=True, blank=True)
    date_published = models.DateTimeField()
    previous_start_date = models.DateTimeField(null=True, blank=True)
    event_status = models.SmallIntegerField(choices=STATUSES, default=SCHEDULED)
    typical_age_range = models.CharField(max_length=255, null=True, blank=True)
    slug = models.SlugField(blank=True)
    categories = models.ManyToManyField(Category, null=True, blank=True)
    offers = models.ManyToManyField(Offer, blank=True)
    super_event = TreeForeignKey('self', null=True, blank=True, related_name='children')

    # Custom fields not from schema.org
    target_group = models.CharField(max_length=255, null=True, blank=True)

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
