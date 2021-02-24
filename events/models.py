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
import logging
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
import pytz
from django.contrib.gis.db import models
from rest_framework.exceptions import ValidationError
from reversion import revisions as reversion
from django.utils.translation import ugettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
from mptt.querysets import TreeQuerySet
from django.contrib.contenttypes.models import ContentType
from events import translation_utils
from django.utils.encoding import python_2_unicode_compatible
from django.contrib.postgres.fields import HStoreField
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.db import transaction
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from image_cropping import ImageRatioField
from munigeo.models import AdministrativeDivision
from notifications.models import render_notification_template, NotificationType, NotificationTemplateException
from smtplib import SMTPException

logger = logging.getLogger(__name__)

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
    owner = models.ForeignKey(
        'django_orghierarchy.Organization', on_delete=models.SET_NULL,
        related_name='owned_systems', null=True, blank=True)
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


class BaseQuerySet(models.QuerySet):
    def is_user_editable(self):
        return not bool(self.filter(data_source__isnull=True) and
                        self.filter(data_source__user_editable=False))

    def can_be_edited_by(self, user):
        """Check if the whole queryset can be edited by the given user"""
        if user.is_superuser:
            return True
        for event in self:
            if not user.can_edit_event(event.publisher, event.publication_status):
                return False
        return True


class BaseTreeQuerySet(TreeQuerySet, BaseQuerySet):
    pass


class ReplacedByMixin():
    def _has_circular_replacement(self):
        replaced_by = self.replaced_by
        while replaced_by is not None:
            replaced_by = replaced_by.replaced_by
            if replaced_by == self:
                return True
        return False

    def get_replacement(self):
        replacement = self.replaced_by
        while replacement.replaced_by is not None:
            replacement = replacement.replaced_by
        return replacement


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
    objects = BaseQuerySet.as_manager()

    # Properties from schema.org/Thing
    name = models.CharField(verbose_name=_('Name'), max_length=255, db_index=True, blank=True, null=True)

    data_source = models.ForeignKey(
        DataSource, on_delete=models.CASCADE, related_name='provided_%(class)s_data', db_index=True, null=True)
    publisher = models.ForeignKey(
        'django_orghierarchy.Organization', on_delete=models.CASCADE, verbose_name=_('Publisher'),
        db_index=True, null=True, blank=True, related_name='Published_images')

    created_time = models.DateTimeField(auto_now_add=True)
    last_modified_time = models.DateTimeField(auto_now=True, db_index=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='EventImage_created_by')
    last_modified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='EventImage_last_modified_by', null=True, blank=True)

    image = models.ImageField(upload_to='images', null=True, blank=True)
    url = models.URLField(verbose_name=_('Image'), max_length=400, null=True, blank=True)
    cropping = ImageRatioField('image', '800x800', verbose_name=_('Cropping'))
    license = models.ForeignKey(
        License, on_delete=models.SET_NULL, verbose_name=_('License'), related_name='images', default='cc_by',
        null=True)
    photographer_name = models.CharField(verbose_name=_('Photographer name'), max_length=255, null=True, blank=True)
    alt_text = models.CharField(verbose_name=_('Alt text'), max_length=320, null=True, blank=True)

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
        return bool(self.data_source and self.data_source.user_editable)

    def is_user_edited(self):
        return bool(self.is_user_editable() and self.last_modified_by)

    def can_be_edited_by(self, user):
        """Check if current image can be edited by the given user"""
        if user.is_superuser:
            return True
        return user.is_admin(self.publisher)


class ImageMixin(models.Model):
    image = models.ForeignKey(Image, verbose_name=_('Image'), on_delete=models.SET_NULL,
                              null=True, blank=True)

    class Meta:
        abstract = True


@python_2_unicode_compatible
class BaseModel(models.Model):
    objects = BaseQuerySet.as_manager()

    id = models.CharField(max_length=100, primary_key=True)
    data_source = models.ForeignKey(
        DataSource, on_delete=models.CASCADE, related_name='provided_%(class)s_data', db_index=True)

    # Properties from schema.org/Thing
    name = models.CharField(verbose_name=_('Name'), max_length=255, db_index=True)

    origin_id = models.CharField(verbose_name=_('Origin ID'), max_length=100, db_index=True, null=True,
                                 blank=True)

    created_time = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    last_modified_time = models.DateTimeField(null=True, blank=True, auto_now=True, db_index=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="%(app_label)s_%(class)s_created_by")
    last_modified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="%(app_label)s_%(class)s_modified_by")

    @staticmethod
    def now():
        return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

    def __str__(self):
        return self.name

    class Meta:
        abstract = True

    def is_user_editable(self):
        return self.data_source.user_editable

    def is_user_edited(self):
        return bool(self.data_source.user_editable and self.last_modified_by)


class Language(models.Model):
    id = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(verbose_name=_('Name'), max_length=20)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('language')
        verbose_name_plural = _('languages')


class KeywordLabel(models.Model):
    name = models.CharField(verbose_name=_('Name'), max_length=255, db_index=True)
    language = models.ForeignKey(Language, on_delete=models.CASCADE, blank=False, null=False)

    def __str__(self):
        return self.name + ' (' + str(self.language) + ')'

    class Meta:
        unique_together = (('name', 'language'),)


class Keyword(BaseModel, ImageMixin, ReplacedByMixin):
    publisher = models.ForeignKey(
        'django_orghierarchy.Organization', on_delete=models.CASCADE, verbose_name=_('Publisher'),
        db_index=True, null=True, blank=True,
        related_name='Published_keywords')
    alt_labels = models.ManyToManyField(KeywordLabel, blank=True, related_name='keywords')
    aggregate = models.BooleanField(default=False)
    deprecated = models.BooleanField(default=False, db_index=True)
    n_events = models.IntegerField(
        verbose_name=_('event count'),
        help_text=_('number of events with this keyword'),
        default=0,
        editable=False,
        db_index=True
    )
    n_events_changed = models.BooleanField(default=False, db_index=True)
    replaced_by = models.ForeignKey(
        'Keyword', on_delete=models.SET_NULL, related_name='aliases', null=True, blank=True)

    schema_org_type = "Thing/LinkedEventKeyword"

    def __str__(self):
        return self.name

    def deprecate(self):
        self.deprecated = True
        self.save(update_fields=['deprecated'])
        return True

    def replace(self, replaced_by):
        self.replaced_by = replaced_by
        self.save(update_fields=['replaced_by'])
        return True

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._has_circular_replacement():
            raise ValidationError(_("Trying to replace this keyword with a keyword that is replaced by this keyword. "
                                    "Please refrain from creating circular replacements and"
                                    "remove one of the replacements."))

        if self.replaced_by and not self.deprecated:
            self.deprecated = True
            logger.warning("Keyword replaced without deprecating. Deprecating automatically", extra={'keyword': self})

        old_replaced_by = None
        if self.id:
            try:
                old_replaced_by = Keyword.objects.get(id=self.id).replaced_by
            except Keyword.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        if not old_replaced_by == self.replaced_by:
            # Remap keyword sets
            qs = KeywordSet.objects.filter(keywords__id__exact=self.id)
            for kw_set in qs:
                kw_set.keywords.remove(self)
                kw_set.keywords.add(self.replaced_by)
                kw_set.save()

            # Remap events
            qs = Event.objects.filter(keywords__id__exact=self.id) \
                | Event.objects.filter(audience__id__exact=self.id)
            for event in qs:
                if self in event.keywords.all():
                    event.keywords.remove(self)
                    event.keywords.add(self.replaced_by)
                if self in event.audience.all():
                    event.audience.remove(self)
                    event.audience.add(self.replaced_by)

    class Meta:
        verbose_name = _('keyword')
        verbose_name_plural = _('keywords')


class KeywordSet(BaseModel, ImageMixin):
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
    organization = models.ForeignKey('django_orghierarchy.Organization', on_delete=models.CASCADE,
                                     verbose_name=_('Organization which uses this set'), null=True)
    keywords = models.ManyToManyField(Keyword, blank=False, related_name='sets')

    def save(self, *args, **kwargs):
        if any([keyword.deprecated for keyword in self.keywords.all()]):
            raise ValidationError(_("KeywordSet can't have deprecated keywords"))
        super().save(*args, **kwargs)


class Place(MPTTModel, BaseModel, SchemalessFieldMixin, ImageMixin, ReplacedByMixin):
    objects = BaseTreeQuerySet.as_manager()
    geo_objects = objects

    publisher = models.ForeignKey(
        'django_orghierarchy.Organization', on_delete=models.CASCADE, verbose_name=_('Publisher'), db_index=True)
    info_url = models.URLField(verbose_name=_('Place home page'), null=True, blank=True, max_length=1000)
    description = models.TextField(verbose_name=_('Description'), null=True, blank=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
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
    replaced_by = models.ForeignKey('Place', on_delete=models.SET_NULL, related_name='aliases', null=True, blank=True)
    divisions = models.ManyToManyField(AdministrativeDivision, verbose_name=_('Divisions'), related_name='places',
                                       blank=True)
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
        if self._has_circular_replacement():
            raise ValidationError(_("Trying to replace this place with a place that is replaced by this place. "
                                    "Please refrain from creating circular replacements and remove one of the "
                                    "replacements. We don't want homeless events."))

        if self.replaced_by and not self.deleted:
            self.deleted = True
            logger.warning("Place replaced without soft deleting. Soft deleting automatically", extra={'place': self})

        # needed to remap events to replaced location
        old_replaced_by = None
        if self.id:
            try:
                old_replaced_by = Place.objects.get(id=self.id).replaced_by
            except Place.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # needed to remap events to replaced location
        if not old_replaced_by == self.replaced_by:
            Event.objects.filter(location=self).update(location=self.replaced_by)
            # Update doesn't call save so we update event numbers manually.
            # Not all of the below are necessarily present.
            ids_to_update = [event.id for event in (self, self.replaced_by, old_replaced_by) if event]
            Place.objects.filter(id__in=ids_to_update).update(n_events_changed=True)

        if self.position:
            self.divisions.set(AdministrativeDivision.objects.filter(
                type__type__in=('district', 'sub_district', 'neighborhood', 'muni'),
                geometry__boundary__contains=self.position))
        else:
            self.divisions.clear()


reversion.register(Place)


class OpeningHoursSpecification(models.Model):
    GR_BASE_URL = "http://purl.org/goodrelations/v1#"
    WEEK_DAYS = (
        (1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"),
        (5, "Friday"), (6, "Saturday"), (7, "Sunday"), (8, "PublicHolidays")
    )

    place = models.ForeignKey(Place, on_delete=models.CASCADE, db_index=True,
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


class Event(MPTTModel, BaseModel, SchemalessFieldMixin, ReplacedByMixin):
    jsonld_type = "Event/LinkedEvent"
    objects = BaseTreeQuerySet.as_manager()

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
        UMBRELLA = 'umbrella'

    SUPER_EVENT_TYPES = (
        (SuperEventType.RECURRING, _('Recurring')),
        (SuperEventType.UMBRELLA, _('Umbrella event')),
    )

    class SubEventType:
        SUB_RECURRING = 'sub_recurring'
        SUB_UMBRELLA = 'sub_umbrella'

    SUB_EVENT_TYPES = (
        (SubEventType.SUB_RECURRING, _('Sub_Recurring')),
        (SubEventType.SUB_UMBRELLA, _('Sub_Umbrella')),
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
    provider_contact_info = models.CharField(verbose_name=_("Provider's contact info"),
                                             max_length=255, null=True, blank=True)
    publisher = models.ForeignKey('django_orghierarchy.Organization', verbose_name=_('Publisher'), db_index=True,
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

    audience_min_age = models.SmallIntegerField(verbose_name=_('Minimum recommended age'),
                                                blank=True, null=True, db_index=True)
    audience_max_age = models.SmallIntegerField(verbose_name=_('Maximum recommended age'),
                                                blank=True, null=True, db_index=True)

    super_event = TreeForeignKey('self', null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='sub_events')

    super_event_type = models.CharField(max_length=255, blank=True, null=True, db_index=True,
                                        default=None, choices=SUPER_EVENT_TYPES)

    sub_event_type = models.CharField(max_length=255, blank=True, null=True, db_index=True, 
                                        default=None, choices=SUB_EVENT_TYPES)

    in_language = models.ManyToManyField(Language, verbose_name=_('In language'), related_name='events', blank=True)

    images = models.ManyToManyField(Image, related_name='events', blank=True)

    deleted = models.BooleanField(default=False, db_index=True)

    is_virtualevent = models.BooleanField(default=False, db_index=True)
    virtualevent_url = models.URLField(verbose_name=_('Virtual event location'), blank=True, null=True, max_length=1000)

    replaced_by = models.ForeignKey('Event', on_delete=models.SET_NULL, related_name='aliases', null=True, blank=True)

    # Custom fields not from schema.org
    keywords = models.ManyToManyField(Keyword, related_name='events')
    audience = models.ManyToManyField(Keyword, related_name='audience_events', blank=True)

    class Meta:
        verbose_name = _('event')
        verbose_name_plural = _('events')

    class MPTTMeta:
        parent_attr = 'super_event'

    def save(self, *args, **kwargs):
        if self._has_circular_replacement():
            raise ValidationError(_("Trying to replace this event with an event that is replaced by this event. "
                                    "Please refrain from creating circular replacements and "
                                    "remove one of the replacements."))

        if self.replaced_by and not self.deleted:
            self.deleted = True
            logger.warning("Event replaced without soft deleting. Soft deleting automatically", extra={'event': self})

        # needed to cache location event numbers
        old_location = None

        # needed for notifications
        old_publication_status = None
        old_deleted = None
        created = True

        if self.id:
            try:
                event = Event.objects.get(id=self.id)
                created = False
                old_location = event.location
                old_publication_status = event.publication_status
                old_deleted = event.deleted
            except Event.DoesNotExist:
                pass

        # drafts may not have times set, so check that first
        start = getattr(self, 'start_time', None)
        end = getattr(self, 'end_time', None)
        if start and end:
            if start > end:
                raise ValidationError({'end_time': _('The event end time cannot be earlier than the start time.')})

        if (self.keywords.filter(deprecated=True) or self.audience.filter(deprecated=True)) and (
                not self.deleted):
            raise ValidationError({'keywords': _("Trying to save event with deprecated keywords " +
                                                 str(self.keywords.filter(deprecated=True).values('id')) + " or " +
                                                 str(self.audience.filter(deprecated=True).values('id')) +
                                                 ". Please use up-to-date keywords.")})

        super(Event, self).save(*args, **kwargs)

        # needed to cache location event numbers
        if not old_location and self.location:
            Place.objects.filter(id=self.location.id).update(n_events_changed=True)
        if old_location and not self.location:
            # drafts (or imported events) may not always have location set
            Place.objects.filter(id=old_location.id).update(n_events_changed=True)
        if old_location and self.location and old_location != self.location:
            Place.objects.filter(id__in=(old_location.id, self.location.id)).update(n_events_changed=True)

        # send notifications
        if old_publication_status == PublicationStatus.DRAFT and self.publication_status == PublicationStatus.PUBLIC:
            self.send_published_notification()
        if self.publication_status == PublicationStatus.DRAFT and (old_deleted is False and self.deleted is True):
            self.send_deleted_notification()
        if created and self.publication_status == PublicationStatus.DRAFT:
            self.send_draft_posted_notification()

    def __str__(self):
        name = ''
        languages = [lang[0] for lang in settings.LANGUAGES]
        for lang in languages:
            lang = lang.replace('-', '_')  # to handle complex codes like e.g. zh-hans
            s = getattr(self, 'name_%s' % lang, None)
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
            return user.is_admin(self.publisher)

    def can_be_edited_by(self, user):
        """Check if current event can be edited by the given user"""
        if user.is_superuser:
            return True
        return user.can_edit_event(self.publisher, self.publication_status)

    def soft_delete(self, using=None):
        self.deleted = True
        self.save(update_fields=("deleted",), using=using, force_update=True)

    def undelete(self, using=None):
        self.deleted = False
        self.save(update_fields=("deleted",), using=using, force_update=True)

    def _send_notification(self, notification_type, recipient_list, request=None):
        if len(recipient_list) == 0:
            logger.warning("No recipients for notification type '%s'" % notification_type, extra={'event': self})
            return
        context = {'event': self}
        try:
            rendered_notification = render_notification_template(notification_type, context)
        except NotificationTemplateException as e:
            logger.error(e, exc_info=True, extra={'request': request})
            return
        try:
            send_mail(
                rendered_notification['subject'],
                rendered_notification['body'],
                'noreply@%s' % Site.objects.get_current().domain,
                recipient_list,
                html_message=rendered_notification['html_body']
            )
        except SMTPException as e:
            logger.error(e, exc_info=True, extra={'request': request, 'event': self})

    def _get_author_emails(self):
        author_emails = []
        author = self.created_by
        if author and author.email:
            author_emails.append(author.email)
        return author_emails

    def send_deleted_notification(self, request=None):
        recipient_list = self._get_author_emails()
        self._send_notification(NotificationType.UNPUBLISHED_EVENT_DELETED, recipient_list, request)

    def send_published_notification(self, request=None):
        recipient_list = self._get_author_emails()
        self._send_notification(NotificationType.EVENT_PUBLISHED, recipient_list, request)

    def send_draft_posted_notification(self, request=None):
        recipient_list = []
        for admin in self.publisher.admin_users.all():
            if admin.email:
                recipient_list.append(admin.email)
        self._send_notification(NotificationType.DRAFT_POSTED, recipient_list, request)


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
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_index=True, related_name='offers')
    price = models.CharField(verbose_name=_('Price'), blank=True, max_length=1000)
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
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_index=True, related_name='external_links')
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    link = models.URLField()

    class Meta:
        unique_together = (('name', 'event', 'language', 'link'),)

    def value_fields(self):
        return ['name', 'language_id', 'link']


class Video(models.Model, SimpleValueMixin):
    name = models.CharField(verbose_name=_('Name'), max_length=255, db_index=True, blank=True, null=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_index=True, related_name='videos')
    url = models.URLField()
    alt_text = models.CharField(verbose_name=_('Alt text'), max_length=320, null=True, blank=True)

    class Meta:
        unique_together = (('name', 'event', 'url'),)

    def value_fields(self):
        return ['name', 'url']


class ExportInfo(models.Model):
    target_id = models.CharField(max_length=255, db_index=True, null=True,
                                 blank=True)
    target_system = models.CharField(max_length=255, db_index=True, null=True,
                                     blank=True)
    last_exported_time = models.DateTimeField(null=True, blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = (('target_system', 'content_type', 'object_id'),)

    def save(self, *args, **kwargs):
        self.last_exported_time = BaseModel.now()
        super(ExportInfo, self).save(*args, **kwargs)


class EventAggregate(models.Model):
    super_event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='aggregate', null=True)


class EventAggregateMember(models.Model):
    event_aggregate = models.ForeignKey(EventAggregate, on_delete=models.CASCADE, related_name='members')
    event = models.OneToOneField(Event, on_delete=models.CASCADE)
