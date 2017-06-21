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
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
import pytz
from django.contrib.gis.db import models
from rest_framework.exceptions import ValidationError
from reversion import revisions as reversion
from django.utils.translation import ugettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
from django.contrib.contenttypes.models import ContentType
from events import translation_utils
from django.utils.encoding import python_2_unicode_compatible
from django.contrib.postgres.fields import HStoreField
from django.db import transaction
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from image_cropping import ImageRatioField
from munigeo.models import AdministrativeDivision


User = settings.AUTH_USER_MODEL

class PublicationStatus:
    PUBLIC = 1
    DRAFT = 2

PUBLICATION_STATUSES = (
    (PublicationStatus.PUBLIC, "public"),
    (PublicationStatus.DRAFT, "draft"),
)


class SchemalessFieldMixin(models.Model):
    custom_data = HStoreField(null=True, blank=True)

    class Meta:
        abstract = True


@python_2_unicode_compatible
class DataSource(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(verbose_name=_('Name'), max_length=255)
    api_key = models.CharField(max_length=128, blank=True, default='')
    owner = models.ForeignKey('Organization', related_name='owned_systems', null=True, blank=True)
    user_editable = models.BooleanField(default=False, verbose_name=_('Objects may be edited by users'))

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


class License(models.Model):
    id = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(verbose_name=_('Name'), max_length=255)
    url = models.URLField(verbose_name=_('Url'), blank=True)

    class Meta:
        verbose_name = _('License')
        verbose_name_plural = _('Licenses')

    def __str__(self):
        return self.name


class Image(models.Model):
    jsonld_type = 'ImageObject'

    # Properties from schema.org/Thing
    name = models.CharField(verbose_name=_('Name'), max_length=255, db_index=True, default='')

    data_source = models.ForeignKey(DataSource, related_name='provided_%(class)s_data', db_index=True, null=True)
    publisher = models.ForeignKey('Organization', verbose_name=_('Publisher'), db_index=True, null=True, blank=True, related_name='Published_images')

    created_time = models.DateTimeField(auto_now_add=True)
    last_modified_time = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, null=True, blank=True, related_name='EventImage_created_by')
    last_modified_by = models.ForeignKey(User, related_name='EventImage_last_modified_by', null=True, blank=True)

    image = models.ImageField(upload_to='images', null=True, blank=True)
    url = models.URLField(verbose_name=_('Image'), max_length=400, null=True, blank=True)
    cropping = ImageRatioField('image', '800x800', verbose_name=_('Cropping'))
    license = models.ForeignKey(License, verbose_name=_('License'), related_name='images', default='cc_by')
    photographer_name = models.CharField(verbose_name=_('Photographer name'), max_length=255, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.publisher:
            try:
                self.publisher = self.created_by.get_default_organization()
            except AttributeError:
                pass
        # ensure that either image or url is provided
        if not self.url and not self.image:
            raise ValidationError(_('You must provide either image or url.'))
        if self.url and self.image:
            raise ValidationError(_('You can only provide image or url, not both.'))
        self.last_modified_time = BaseModel.now()
        super(Image, self).save(*args, **kwargs)

    def is_user_editable(self):
        return self.data_source.user_editable

    def is_user_edited(self):
        return bool(self.data_source.user_editable and self.last_modified_by)

    def is_admin(self, user):
        if user.is_superuser:
            return True
        else:
            return user in self.publisher.admin_users.all()


@python_2_unicode_compatible
class BaseModel(models.Model):
    id = models.CharField(max_length=50, primary_key=True)
    data_source = models.ForeignKey(DataSource, related_name='provided_%(class)s_data', db_index=True)

    # Properties from schema.org/Thing
    name = models.CharField(verbose_name=_('Name'), max_length=255, db_index=True)

    origin_id = models.CharField(verbose_name=_('Origin ID'), max_length=50, db_index=True, null=True,
                                 blank=True)

    created_time = models.DateTimeField(null=True, blank=True)
    last_modified_time = models.DateTimeField(null=True, blank=True, db_index=True)

    created_by = models.ForeignKey(
        User, null=True, blank=True,
        related_name="%(app_label)s_%(class)s_created_by")
    last_modified_by = models.ForeignKey(
        User, null=True, blank=True,
        related_name="%(app_label)s_%(class)s_modified_by")
    image = models.ForeignKey(Image, verbose_name=_('Image'), on_delete=models.SET_NULL,
                              null=True, blank=True)

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

    def is_user_editable(self):
        return self.data_source.user_editable

    def is_user_edited(self):
        return bool(self.data_source.user_editable and self.last_modified_by)


class Organization(BaseModel):
    admin_users = models.ManyToManyField(
        User, blank=True, related_name='admin_organizations'
    )

    class Meta:
        ordering = ('name',)
        verbose_name =_('organization')
        verbose_name_plural = _('organizations')


class Language(models.Model):
    id = models.CharField(max_length=6, primary_key=True)
    name = models.CharField(verbose_name=_('Name'), max_length=20)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('language')
        verbose_name_plural = _('languages')


class KeywordLabel(models.Model):
    name = models.CharField(verbose_name=_('Name'), max_length=255, db_index=True)
    language = models.ForeignKey(Language, blank=False, null=False)

    def __str__(self):
        return self.name + ' (' + str(self.language) + ')'

    class Meta:
        unique_together = (('name', 'language'),)


class Keyword(BaseModel):
    alt_labels = models.ManyToManyField(KeywordLabel, blank=True, related_name='keywords')
    aggregate = models.BooleanField(default=False)
    deprecated = models.BooleanField(default=False, db_index=True)
    objects = models.Manager()
    n_events = models.IntegerField(
        verbose_name=_('event count'),
        help_text=_('number of events with this keyword'),
        default=0,
        editable=False,
        db_index=True
    )
    n_events_changed = models.BooleanField(default=False, db_index=True)

    schema_org_type = "Thing/LinkedEventKeyword"

    def __str__(self):
        return self.name

    def deprecate(self):
        self.deprecated = True
        self.save(update_fields=['deprecated'])
        return True

    class Meta:
        verbose_name = _('keyword')
        verbose_name_plural = _('keywords')


class KeywordSet(BaseModel):
    """
    Sets of pre-chosen keywords intended or specific uses and/or organizations,
    for example the set of possible audiences for an event in a specific client.
    """

    ANY = 1
    KEYWORD = 2
    AUDIENCE = 3

    USAGES = (
        (ANY, "any"),
        (KEYWORD, "keyword"),
        (AUDIENCE, "audience"),
    )
    usage = models.SmallIntegerField(verbose_name=_('Intended keyword usage'), choices=USAGES, default=ANY)
    organization = models.ForeignKey(Organization, verbose_name=_('Organization which uses this set'), null=True)
    keywords = models.ManyToManyField(Keyword, blank=False, related_name='sets')


class Place(MPTTModel, BaseModel, SchemalessFieldMixin):
    publisher = models.ForeignKey(Organization, verbose_name=_('Publisher'), db_index=True)
    info_url = models.URLField(verbose_name=_('Place home page'), blank=True, default='', max_length=1000)
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
    divisions = models.ManyToManyField(AdministrativeDivision, verbose_name=_('Divisions'), related_name='places',
                                       blank=True)

    geo_objects = models.GeoManager()
    n_events = models.IntegerField(
        verbose_name=_('event count'),
        help_text=_('number of events in this location'),
        default=0,
        editable=False,
        db_index=True
    )
    n_events_changed = models.BooleanField(default=False, db_index=True)


    class Meta:
        verbose_name = _('place')
        verbose_name_plural = _('places')
        unique_together = (('data_source', 'origin_id'),)

    def __unicode__(self):
        values = filter(lambda x: x, [
            self.street_address, self.postal_code, self.address_locality
        ])
        return u', '.join(values)

    @transaction.atomic
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.position:
            self.divisions = AdministrativeDivision.objects.filter(
                type__type__in=('district', 'sub_district', 'neighborhood', 'muni'),
                geometry__boundary__contains=self.position)
        else:
            self.divisions.clear()

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

    class Status:
        SCHEDULED = 1
        CANCELLED = 2
        POSTPONED = 3
        RESCHEDULED = 4
    # Properties from schema.org/Event
    STATUSES = (
        (Status.SCHEDULED, "EventScheduled"),
        (Status.CANCELLED, "EventCancelled"),
        (Status.POSTPONED, "EventPostponed"),
        (Status.RESCHEDULED, "EventRescheduled"),
    )

    class SuperEventType:
        RECURRING = 'recurring'

    SUPER_EVENT_TYPES = (
        (SuperEventType.RECURRING, _('Recurring')),
        # Other types include e.g. a festival
    )

    # Properties from schema.org/Thing
    info_url = models.URLField(verbose_name=_('Event home page'), blank=True, null=True, max_length=1000)
    description = models.TextField(verbose_name=_('Description'), blank=True, null=True)
    short_description = models.TextField(verbose_name=_('Short description'), blank=True, null=True)

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
    secondary_headline = models.CharField(verbose_name=_('Secondary headline'), max_length=255,
                                          null=True, db_index=True)
    provider = models.CharField(verbose_name=_('Provider'), max_length=512, null=True)
    publisher = models.ForeignKey(Organization, verbose_name=_('Publisher'), db_index=True,
                                  on_delete=models.PROTECT, related_name='published_events')

    # Status of the event itself
    event_status = models.SmallIntegerField(verbose_name=_('Event status'), choices=STATUSES,
                                            default=Status.SCHEDULED)

    # Whether or not this data about the event is ready to be viewed by the general public.
    # DRAFT means the data is considered incomplete or is otherwise undergoing refinement --
    # or just waiting to be published for other reasons.
    publication_status = models.SmallIntegerField(
        verbose_name=_('Event data publication status'), choices=PUBLICATION_STATUSES,
        default=PublicationStatus.PUBLIC)

    location = models.ForeignKey(Place, related_name='events', null=True, blank=True, on_delete=models.PROTECT)
    location_extra_info = models.CharField(verbose_name=_('Location extra info'),
                                           max_length=400, null=True, blank=True)

    start_time = models.DateTimeField(verbose_name=_('Start time'), null=True, db_index=True, blank=True)
    end_time = models.DateTimeField(verbose_name=_('End time'), null=True, db_index=True, blank=True)
    has_start_time = models.BooleanField(default=True)
    has_end_time = models.BooleanField(default=True)

    super_event = TreeForeignKey('self', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='sub_events')

    super_event_type = models.CharField(max_length=255, blank=True, null=True, default=None, choices=SUPER_EVENT_TYPES)

    in_language = models.ManyToManyField(Language, verbose_name=_('In language'), related_name='events', blank=True)

    deleted = models.BooleanField(default=False, db_index=True)

    # Custom fields not from schema.org
    keywords = models.ManyToManyField(Keyword, related_name='events')
    audience = models.ManyToManyField(Keyword, related_name='audience_events', blank=True)

    class Meta:
        verbose_name = _('event')
        verbose_name_plural = _('events')

    class MPTTMeta:
        parent_attr = 'super_event'

    def save(self, *args, **kwargs):
        # needed to cache location event numbers
        old_location = None
        if self.id:
            try:
                old_location = Event.objects.get(id=self.id).location
            except Event.DoesNotExist:
                pass

        # drafts may not have times set, so check that first
        start = getattr(self, 'start_time', None)
        end = getattr(self, 'end_time', None)
        if start and end:
            if start > end:
                raise ValidationError({'end_time': _('The event end time cannot be earlier than the start time.')})
        if not self.id:
            self.created_time = BaseModel.now()
        self.last_modified_time = BaseModel.now()

        super(Event, self).save(*args, **kwargs)

        # needed to cache location event numbers
        if not old_location and self.location:
            Place.objects.filter(id=self.location.id).update(n_events_changed=True)
        if old_location and old_location != self.location:
            Place.objects.filter(id__in=(old_location.id, self.location.id)).update(n_events_changed=True)

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

    def is_admin(self, user):
        if user.is_superuser:
            return True
        else:
            return user in self.publisher.admin_users.all()

reversion.register(Event)


@receiver(m2m_changed, sender=Event.keywords.through)
@receiver(m2m_changed, sender=Event.audience.through)
def keyword_added_or_removed(sender, model=None,
                             instance=None, pk_set=None, action=None, **kwargs):
    """
    Listens to event-keyword add signals to keep event number up to date
    """
    if action in ('post_add', 'post_remove'):
        if model is Keyword:
            Keyword.objects.filter(pk__in=pk_set).update(n_events_changed=True)
        if model is Event:
            instance.n_events_changed = True
            instance.save(update_fields=("n_events_changed",))


class Offer(models.Model, SimpleValueMixin):
    event = models.ForeignKey(Event, db_index=True, related_name='offers')
    price = models.CharField(verbose_name=_('Price'), blank=True, max_length=512)
    info_url = models.URLField(verbose_name=_('Web link to offer'), blank=True, null=True, max_length=1000)
    description = models.TextField(verbose_name=_('Offer description'), blank=True, null=True)
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
        unique_together = (('name', 'event', 'language', 'link'),)

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
    event = models.OneToOneField(Event)
