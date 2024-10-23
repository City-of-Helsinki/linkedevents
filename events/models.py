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

import pytz
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.contrib.postgres.fields import HStoreField
from django.contrib.postgres.indexes import Index
from django.contrib.postgres.search import SearchVectorField
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from image_cropping import ImageRatioField
from mptt.managers import TreeManager
from mptt.models import MPTTModel, TreeForeignKey
from mptt.querysets import TreeQuerySet
from munigeo.models import AdministrativeDivision
from rest_framework.exceptions import ValidationError
from reversion import revisions as reversion

from events import translation_utils
from events.translation_utils import TranslatableSerializableMixin
from notifications.models import (
    NotificationTemplateException,
    NotificationType,
    render_notification_template,
)
from notifications.utils import format_date, format_datetime
from registrations.utils import get_email_noreply_address

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


class DataSource(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(verbose_name=_("Name"), max_length=255)
    api_key = models.CharField(max_length=128, blank=True, default="")
    owner = models.ForeignKey(
        "django_orghierarchy.Organization",
        on_delete=models.SET_NULL,
        related_name="owned_systems",
        null=True,
        blank=True,
    )
    user_editable_resources = models.BooleanField(
        default=False, verbose_name=_("Resources may be edited by users")
    )
    user_editable_organizations = models.BooleanField(
        default=False, verbose_name=_("Organizations may be edited by users")
    )
    user_editable_registrations = models.BooleanField(
        default=False,
        verbose_name=_("Owner organization's registrations may be edited by users"),
    )
    user_editable_registration_price_groups = models.BooleanField(
        default=False,
        verbose_name=_(
            "Owner organization's registration price groups may be edited by users"
        ),
    )
    edit_past_events = models.BooleanField(
        default=False, verbose_name=_("Past events may be edited using API")
    )
    create_past_events = models.BooleanField(
        default=False, verbose_name=_("Past events may be created using API")
    )
    private = models.BooleanField(
        default=False,
        verbose_name=_("Do not show events created by this data_source by default."),
        db_index=True,
    )

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
    def is_user_editable_resources(self):
        return not bool(
            self.filter(data_source__isnull=True)
            and self.filter(data_source__user_editable_resources=False)
        )

    def can_be_edited_by(self, user):
        """Check if the whole queryset can be edited by the given user"""
        if user.is_superuser:
            return True
        for event in self:
            if not user.can_edit_event(
                event.publisher, event.publication_status, event.created_by
            ):
                return False
        return True


class BaseSerializableManager(TranslatableSerializableMixin.SerializableManager):
    def get_queryset(self):
        return BaseQuerySet(self.model, using=self._db)


class BaseTreeQuerySet(TreeQuerySet, BaseQuerySet):
    def soft_delete(self):
        return self.filter(deleted=False).update(
            deleted=True, last_modified_time=timezone.now()
        )

    soft_delete.alters_data = True

    def undelete(self):
        return self.filter(deleted=True).update(
            deleted=False, last_modified_time=timezone.now()
        )

    undelete.alters_data = True


class BaseSerializableTreeManager(
    TreeManager, TranslatableSerializableMixin.SerializableManager
):
    def get_queryset(self):
        return BaseTreeQuerySet(self.model, using=self._db).order_by(
            self.tree_id_attr, self.left_attr
        )


class ReplacedByMixin:
    def _has_circular_replacement(self):
        replaced_by = self.replaced_by
        while replaced_by is not None:
            replaced_by = replaced_by.replaced_by
            if replaced_by == self:
                return True
        return False

    def get_replacement(self):
        replacement = self.replaced_by

        if replacement is None:
            return None

        while replacement.replaced_by is not None:
            replacement = replacement.replaced_by
        return replacement


class License(models.Model):
    id = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(verbose_name=_("Name"), max_length=255)
    url = models.URLField(verbose_name=_("Url"), blank=True)

    class Meta:
        verbose_name = _("License")
        verbose_name_plural = _("Licenses")

    def __str__(self):
        return self.name


class Image(TranslatableSerializableMixin):
    serialize_fields = [{"name": "name"}, {"name": "url"}]

    jsonld_type = "ImageObject"
    objects = BaseSerializableManager()

    # Properties from schema.org/Thing
    name = models.CharField(
        verbose_name=_("Name"), max_length=255, db_index=True, default=""
    )

    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="provided_%(class)s_data",
        db_index=True,
        null=True,
    )
    publisher = models.ForeignKey(
        "django_orghierarchy.Organization",
        on_delete=models.CASCADE,
        verbose_name=_("Publisher"),
        db_index=True,
        null=True,
        blank=True,
        related_name="Published_images",
    )

    created_time = models.DateTimeField(auto_now_add=True)
    last_modified_time = models.DateTimeField(auto_now=True, db_index=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="EventImage_created_by",
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="EventImage_last_modified_by",
        null=True,
        blank=True,
    )

    image = models.ImageField(upload_to="images", max_length=255, null=True, blank=True)
    url = models.URLField(
        verbose_name=_("Image"), max_length=400, null=True, blank=True
    )
    cropping = ImageRatioField("image", "800x800", verbose_name=_("Cropping"))
    license = models.ForeignKey(
        License,
        on_delete=models.SET_NULL,
        verbose_name=_("License"),
        related_name="images",
        default="cc_by",
        null=True,
    )
    photographer_name = models.CharField(
        verbose_name=_("Photographer name"), max_length=255, null=True, blank=True
    )
    alt_text = models.CharField(
        verbose_name=_("Alt text"), max_length=320, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if not self.publisher:
            try:
                self.publisher = self.created_by.get_default_organization()
            except AttributeError:
                pass
        # ensure that either image or url is provided
        if not self.url and not self.image:
            raise ValidationError(_("You must provide either image or url."))
        if self.url and self.image:
            raise ValidationError(_("You can only provide image or url, not both."))
        self.last_modified_time = BaseModel.now()
        super().save(*args, **kwargs)

    def is_user_editable_resources(self):
        return bool(
            self.data_source is None
            or (self.data_source and self.data_source.user_editable_resources)
        )

    def is_user_edited(self):
        return bool(self.is_user_editable_resources() and self.last_modified_by)

    def can_be_edited_by(self, user):
        """Check if current image can be edited by the given user"""
        if user.is_anonymous:
            return False
        if (
            user.is_external
            and settings.ENABLE_EXTERNAL_USER_EVENTS
            and (
                self.publisher is None
                or self.publisher.id == settings.EXTERNAL_USER_PUBLISHER_ID
            )
        ):
            return self.created_by == user
        return (
            user.is_superuser
            or user.is_admin_of(self.publisher)
            or user.is_regular_user_of(self.publisher)
        )

    def can_be_deleted_by(self, user):
        """Check if current image can be deleted by the given user"""
        if user.is_superuser:
            return True
        return user.is_admin_of(self.publisher)


class ImageMixin(models.Model):
    image = models.ForeignKey(
        Image, verbose_name=_("Image"), on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        abstract = True


class BaseModel(models.Model):
    objects = BaseQuerySet.as_manager()

    id = models.CharField(max_length=100, primary_key=True)
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="provided_%(class)s_data",
        db_index=True,
    )

    # Properties from schema.org/Thing
    name = models.CharField(verbose_name=_("Name"), max_length=255, db_index=True)

    origin_id = models.CharField(
        verbose_name=_("Origin ID"),
        max_length=100,
        db_index=True,
        null=True,
        blank=True,
    )

    created_time = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    last_modified_time = models.DateTimeField(
        null=True, blank=True, auto_now=True, db_index=True
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created_by",
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_modified_by",
    )

    @staticmethod
    def now():
        return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

    def __str__(self):
        return self.name

    class Meta:
        abstract = True

    def is_user_editable_resources(self):
        return self.data_source.user_editable_resources

    def is_user_edited(self):
        return bool(self.data_source.user_editable_resources and self.last_modified_by)

    def save(self, update_fields=None, skip_last_modified_time=False, **kwargs):
        # When saving with update_fields, django will not automatically update
        # last_modified_time.
        if (
            not skip_last_modified_time
            and update_fields is not None
            and "last_modified_time" not in update_fields
        ):
            update_fields = list(update_fields) + ["last_modified_time"]
            if (
                self.last_modified_by_id is not None
                and "last_modified_by" not in update_fields
            ):
                self.last_modified_by = None
                update_fields.append("last_modified_by")

        super().save(update_fields=update_fields, **kwargs)


class Language(TranslatableSerializableMixin):
    serialize_fields = [
        {"name": "name"},
        {"name": "service_language"},
    ]

    id = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(verbose_name=_("Name"), max_length=20)
    service_language = models.BooleanField(
        default=False, verbose_name=_("Can be used as registration service language")
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("language")
        verbose_name_plural = _("languages")


class KeywordLabel(TranslatableSerializableMixin):
    serialize_fields = [
        {"name": "name"},
        {"name": "language"},
    ]

    name = models.CharField(verbose_name=_("Name"), max_length=255, db_index=True)
    language = models.ForeignKey(
        Language, on_delete=models.CASCADE, blank=False, null=False
    )
    search_vector_fi = SearchVectorField(null=True)
    search_vector_en = SearchVectorField(null=True)
    search_vector_sv = SearchVectorField(null=True)

    def __str__(self):
        return self.name + " (" + str(self.language) + ")"

    class Meta:
        unique_together = (("name", "language"),)


class UpcomingEventsUpdater(BaseSerializableManager):
    def has_upcoming_events_update(self):
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        qs = self.model.objects.filter(n_events__gte=1)
        if self.model.__name__ == "Keyword":
            qs = qs.filter(deprecated=False)
        elif self.model.__name__ == "Place":
            qs = qs.filter(deleted=False)
        qs.filter(events__end_time__gte=now).update(has_upcoming_events=True)
        qs.exclude(events__end_time__gte=now).update(has_upcoming_events=False)


class Keyword(BaseModel, ImageMixin, ReplacedByMixin, TranslatableSerializableMixin):
    serialize_fields = [
        {"name": "alt_labels"},
    ]

    publisher = models.ForeignKey(
        "django_orghierarchy.Organization",
        on_delete=models.CASCADE,
        verbose_name=_("Publisher"),
        db_index=True,
        null=True,
        blank=True,
        related_name="Published_keywords",
    )
    alt_labels = models.ManyToManyField(
        KeywordLabel, blank=True, related_name="keywords"
    )
    aggregate = models.BooleanField(default=False)
    deprecated = models.BooleanField(default=False, db_index=True)
    has_upcoming_events = models.BooleanField(default=False, db_index=True)
    n_events = models.IntegerField(
        verbose_name=_("event count"),
        help_text=_("number of events with this keyword"),
        default=0,
        editable=False,
        db_index=True,
    )
    n_events_changed = models.BooleanField(default=False, db_index=True)
    replaced_by = models.ForeignKey(
        "Keyword",
        on_delete=models.SET_NULL,
        related_name="aliases",
        null=True,
        blank=True,
    )

    schema_org_type = "Thing/LinkedEventKeyword"

    objects = UpcomingEventsUpdater()

    def __str__(self):
        return self.name

    def is_admin(self, user):
        if user.is_superuser:
            return True
        else:
            return user in self.publisher.admin_users.all()

    def deprecate(self):
        self.deprecated = True
        self.save(update_fields=["deprecated"])
        return True

    def replace(self, replaced_by):
        self.replaced_by = replaced_by
        self.save(update_fields=["replaced_by"])
        return True

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._has_circular_replacement():
            raise ValidationError(
                _(
                    "Trying to replace this keyword with a keyword that is replaced by this keyword. "  # noqa: E501
                    "Please refrain from creating circular replacements and"
                    "remove one of the replacements."
                )
            )

        if self.replaced_by and not self.deprecated:
            self.deprecated = True
            logger.warning(
                "Keyword replaced without deprecating. Deprecating automatically",
                extra={"keyword": self},
            )

        old_replaced_by = None
        if self.id:
            try:
                old_replaced_by = Keyword.objects.get(id=self.id).get_replacement()
            except Keyword.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        if not old_replaced_by == self.get_replacement():
            # Remap keyword sets
            qs = KeywordSet.objects.filter(keywords__id__exact=self.id)
            for kw_set in qs:
                kw_set.keywords.remove(self)
                kw_set.keywords.add(self.get_replacement())
                kw_set.save()

            # Remap events
            qs = Event.objects.filter(
                keywords__id__exact=self.id
            ) | Event.objects.filter(audience__id__exact=self.id)
            for event in qs:
                if self in event.keywords.all():
                    event.keywords.remove(self)
                    event.keywords.add(self.get_replacement())
                if self in event.audience.all():
                    event.audience.remove(self)
                    event.audience.add(self.get_replacement())

    def can_be_edited_by(self, user):
        """Check if current keyword can be edited by the given user"""
        if user.is_superuser:
            return True
        return user.is_admin_of(self.publisher)

    class Meta:
        verbose_name = _("keyword")
        verbose_name_plural = _("keywords")
        indexes = [
            Index(
                name="keywords_index",
                fields=("name", "name_fi"),
                condition=Q(n_events__gt=0),
            )
        ]


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
    usage = models.SmallIntegerField(
        verbose_name=_("Intended keyword usage"), choices=USAGES, default=ANY
    )
    organization = models.ForeignKey(
        "django_orghierarchy.Organization",
        on_delete=models.CASCADE,
        verbose_name=_("Organization which uses this set"),
        null=True,
    )
    keywords = models.ManyToManyField(Keyword, blank=False, related_name="sets")

    def can_be_edited_by(self, user):
        """Check if current keyword set can be edited by the given user"""
        if user.is_superuser:
            return True
        return user.is_admin_of(self.organization)

    def save(self, *args, **kwargs):
        if any([keyword.deprecated for keyword in self.keywords.all()]):
            raise ValidationError(_("KeywordSet can't have deprecated keywords"))
        super().save(*args, **kwargs)


class Place(
    MPTTModel,
    BaseModel,
    SchemalessFieldMixin,
    ImageMixin,
    ReplacedByMixin,
    TranslatableSerializableMixin,
):
    serialize_fields = [
        {"name": "name"},
        {
            "name": "publisher",
            "accessor": lambda x: (f"{x.id} - {x.name}") if x else "",
        },
        {"name": "info_url"},
        {"name": "description"},
        {"name": "email"},
        {"name": "telephone"},
        {"name": "street_address"},
        {"name": "address_locality"},
        {"name": "address_region"},
        {"name": "postal_code"},
        {"name": "post_office_box_num"},
        {"name": "address_country"},
    ]

    objects = BaseSerializableTreeManager()
    upcoming_events = UpcomingEventsUpdater()

    geo_objects = objects

    publisher = models.ForeignKey(
        "django_orghierarchy.Organization",
        on_delete=models.CASCADE,
        verbose_name=_("Publisher"),
        db_index=True,
    )
    info_url = models.URLField(
        verbose_name=_("Place home page"), null=True, blank=True, max_length=1000
    )
    description = models.TextField(verbose_name=_("Description"), null=True, blank=True)
    parent = TreeForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )

    position = models.PointField(srid=settings.PROJECTION_SRID, null=True, blank=True)

    email = models.EmailField(verbose_name=_("E-mail"), null=True, blank=True)
    telephone = models.CharField(
        verbose_name=_("Telephone"), max_length=128, null=True, blank=True
    )
    contact_type = models.CharField(
        verbose_name=_("Contact type"), max_length=255, null=True, blank=True
    )
    street_address = models.CharField(
        verbose_name=_("Street address"), max_length=255, null=True, blank=True
    )
    address_locality = models.CharField(
        verbose_name=_("Address locality"), max_length=255, null=True, blank=True
    )
    address_region = models.CharField(
        verbose_name=_("Address region"), max_length=255, null=True, blank=True
    )
    postal_code = models.CharField(
        verbose_name=_("Postal code"), max_length=128, null=True, blank=True
    )
    post_office_box_num = models.CharField(
        verbose_name=_("PO BOX"), max_length=128, null=True, blank=True
    )
    address_country = models.CharField(
        verbose_name=_("Country"), max_length=2, null=True, blank=True
    )

    deleted = models.BooleanField(verbose_name=_("Deleted"), default=False)
    replaced_by = models.ForeignKey(
        "Place",
        on_delete=models.SET_NULL,
        related_name="aliases",
        null=True,
        blank=True,
    )
    divisions = models.ManyToManyField(
        AdministrativeDivision,
        verbose_name=_("Divisions"),
        related_name="places",
        blank=True,
    )
    has_upcoming_events = models.BooleanField(default=False, db_index=True)
    n_events = models.IntegerField(
        verbose_name=_("event count"),
        help_text=_("number of events in this location"),
        default=0,
        editable=False,
        db_index=True,
    )
    n_events_changed = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = _("place")
        verbose_name_plural = _("places")
        unique_together = (("data_source", "origin_id"),)

    def __str__(self):
        values = filter(
            lambda x: x, [self.street_address, self.postal_code, self.address_locality]
        )
        return ", ".join(values)

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._has_circular_replacement():
            raise ValidationError(
                _(
                    "Trying to replace this place with a place that is replaced by this place. "  # noqa: E501
                    "Please refrain from creating circular replacements and remove one of the "  # noqa: E501
                    "replacements. We don't want homeless events."
                )
            )

        if self.replaced_by and not self.deleted:
            self.deleted = True
            logger.warning(
                "Place replaced without soft deleting. Soft deleting automatically",
                extra={"place": self},
            )

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
            ids_to_update = [
                event.id for event in (self, self.replaced_by, old_replaced_by) if event
            ]
            Place.objects.filter(id__in=ids_to_update).update(n_events_changed=True)

        if self.position:
            self.divisions.set(
                AdministrativeDivision.objects.filter(
                    type__type__in=("district", "sub_district", "neighborhood", "muni"),
                    geometry__boundary__contains=self.position,
                )
            )
        else:
            self.divisions.clear()

    def is_admin(self, user):
        if user.is_superuser:
            return True
        else:
            return user in self.publisher.admin_users.all()

    def soft_delete(self, using=None):
        self.deleted = True
        self.save(update_fields=("deleted",), using=using, force_update=True)

    def undelete(self, using=None):
        self.deleted = False
        self.save(update_fields=("deleted",), using=using, force_update=True)

    def can_be_edited_by(self, user):
        """Check if current place can be edited by the given user"""
        if user.is_superuser:
            return True
        return user.is_admin_of(self.publisher)


reversion.register(Place)


class OpeningHoursSpecification(models.Model):
    GR_BASE_URL = "http://purl.org/goodrelations/v1#"
    WEEK_DAYS = (
        (1, "Monday"),
        (2, "Tuesday"),
        (3, "Wednesday"),
        (4, "Thursday"),
        (5, "Friday"),
        (6, "Saturday"),
        (7, "Sunday"),
        (8, "PublicHolidays"),
    )

    place = models.ForeignKey(
        Place, on_delete=models.CASCADE, db_index=True, related_name="opening_hours"
    )
    opens = models.TimeField(null=True, blank=True)
    closes = models.TimeField(null=True, blank=True)
    days_of_week = models.SmallIntegerField(choices=WEEK_DAYS, null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_through = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("opening hour specification")
        verbose_name_plural = _("opening hour specifications")


class Event(
    MPTTModel,
    BaseModel,
    SchemalessFieldMixin,
    ReplacedByMixin,
    TranslatableSerializableMixin,
):
    jsonld_type = "Event/LinkedEvent"
    objects = BaseSerializableTreeManager()

    base_serialize_fields = [
        {"name": "id"},
        {"name": "name"},
        {"name": "description"},
        {"name": "short_description"},
        {"name": "start_time"},
        {"name": "end_time"},
        {"name": "images"},
        {"name": "keywords"},
        {
            "name": "publisher",
            "accessor": lambda x: (f"{x.id} - {x.name}") if x else "",
        },
        {"name": "in_language"},
        {"name": "location"},
        {"name": "offers"},
        {"name": "videos"},
        {"name": "audience"},
        {"name": "info_url"},
    ]
    serialize_user_fields = base_serialize_fields + [
        {"name": "user_email"},
        {"name": "user_name"},
        {"name": "user_phone_number"},
        {"name": "user_organization"},
        {"name": "user_consent"},
    ]

    def serialize(self):
        email = getattr(self.created_by, "email", None)

        if email and email == self.user_email:
            self.serialize_fields = self.serialize_user_fields
        else:
            self.serialize_fields = self.base_serialize_fields

        return super().serialize()

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
        RECURRING = "recurring"
        UMBRELLA = "umbrella"

    SUPER_EVENT_TYPES = (
        (SuperEventType.RECURRING, _("Recurring")),
        (SuperEventType.UMBRELLA, _("Umbrella event")),
    )

    class TypeId:
        GENERAL = 1
        COURSE = 2
        VOLUNTEERING = 3

    TYPE_IDS = (
        (TypeId.GENERAL, "General"),
        (TypeId.COURSE, "Course"),
        (TypeId.VOLUNTEERING, "Volunteering"),
    )

    class EventEnvironment(models.TextChoices):
        OUTDOORS = "out", _("Outdoors")
        INDOORS = "in", _("Indoors")

    # External user fields
    user_name = models.CharField(
        verbose_name=_("User name"), max_length=50, blank=True, null=True
    )
    user_email = models.EmailField(verbose_name=_("User e-mail"), blank=True, null=True)
    user_phone_number = models.CharField(
        verbose_name=_("User phone number"),
        max_length=18,
        blank=True,
        null=True,
    )
    user_organization = models.CharField(
        verbose_name=_("User organization"),
        help_text=_("Event organizer information."),
        max_length=255,
        blank=True,
        null=True,
    )
    user_consent = models.BooleanField(
        verbose_name=_("User consent"),
        help_text=_("I consent to the processing of my personal data?"),
        default=False,
    )

    # Properties from schema.org/Thing
    info_url = models.URLField(
        verbose_name=_("Event home page"), blank=True, null=True, max_length=1000
    )
    description = models.TextField(verbose_name=_("Description"), blank=True, null=True)
    short_description = models.TextField(
        verbose_name=_("Short description"), blank=True, null=True
    )

    # Properties from schema.org/CreativeWork
    date_published = models.DateTimeField(
        verbose_name=_("Date published"), null=True, blank=True
    )
    # headline and secondary_headline are for cases where
    # the original event data contains a title and a subtitle - in that
    # case the name field is combined from these.
    #
    # secondary_headline is mapped to schema.org alternative_headline
    # and is used for subtitles, that is for
    # secondary, complementary headlines, not "alternative" headlines
    headline = models.CharField(
        verbose_name=_("Headline"), max_length=255, null=True, db_index=True
    )
    secondary_headline = models.CharField(
        verbose_name=_("Secondary headline"), max_length=255, null=True, db_index=True
    )
    provider = models.CharField(verbose_name=_("Provider"), max_length=512, null=True)
    provider_contact_info = models.CharField(
        verbose_name=_("Provider's contact info"),
        max_length=10000,
        null=True,
        blank=True,
    )
    publisher = models.ForeignKey(
        "django_orghierarchy.Organization",
        verbose_name=_("Publisher"),
        db_index=True,
        on_delete=models.PROTECT,
        related_name="published_events",
    )
    environmental_certificate = models.CharField(
        verbose_name=_("Environmental certificate"),
        max_length=255,
        blank=True,
        null=True,
    )

    # Status of the event itself
    event_status = models.SmallIntegerField(
        verbose_name=_("Event status"), choices=STATUSES, default=Status.SCHEDULED
    )

    # Whether or not this data about the event is ready to be viewed by the general public.  # noqa: E501
    # DRAFT means the data is considered incomplete or is otherwise undergoing refinement --  # noqa: E501
    # or just waiting to be published for other reasons.
    publication_status = models.SmallIntegerField(
        verbose_name=_("Event data publication status"),
        choices=PUBLICATION_STATUSES,
        default=PublicationStatus.PUBLIC,
    )

    location = models.ForeignKey(
        Place, related_name="events", null=True, blank=True, on_delete=models.PROTECT
    )
    location_extra_info = models.CharField(
        verbose_name=_("Location extra info"), max_length=400, null=True, blank=True
    )
    environment = models.CharField(
        verbose_name=_("Event environment"),
        help_text=_("Will the event be held outdoors?"),
        max_length=3,
        choices=EventEnvironment.choices,
        blank=True,
        null=True,
    )

    start_time = models.DateTimeField(
        verbose_name=_("Start time"), null=True, db_index=True, blank=True
    )
    end_time = models.DateTimeField(
        verbose_name=_("End time"), null=True, db_index=True, blank=True
    )
    has_start_time = models.BooleanField(default=True)
    has_end_time = models.BooleanField(default=True)

    audience_min_age = models.PositiveSmallIntegerField(
        verbose_name=_("Minimum recommended age"), blank=True, null=True, db_index=True
    )
    audience_max_age = models.PositiveSmallIntegerField(
        verbose_name=_("Maximum recommended age"), blank=True, null=True, db_index=True
    )

    super_event = TreeForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sub_events",
    )

    super_event_type = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        default=None,
        choices=SUPER_EVENT_TYPES,
    )

    type_id = models.PositiveSmallIntegerField(
        db_index=True, default=TypeId.GENERAL, choices=TYPE_IDS
    )

    in_language = models.ManyToManyField(
        Language, verbose_name=_("In language"), related_name="events", blank=True
    )

    images = models.ManyToManyField(Image, related_name="events", blank=True)

    deleted = models.BooleanField(default=False, db_index=True)

    replaced_by = models.ForeignKey(
        "Event",
        on_delete=models.SET_NULL,
        related_name="aliases",
        null=True,
        blank=True,
    )

    maximum_attendee_capacity = models.PositiveIntegerField(
        verbose_name=_("maximum attendee capacity"), null=True, blank=True
    )

    # TODO: make into agreement with schema.org
    # Custom fields not from schema.org
    minimum_attendee_capacity = models.PositiveIntegerField(
        verbose_name=_("minimum attendee capacity"), null=True, blank=True
    )
    enrolment_start_time = models.DateTimeField(
        verbose_name=_("enrolment start time"), null=True, blank=True
    )
    enrolment_end_time = models.DateTimeField(
        verbose_name=_("enrolment end time"), null=True, blank=True
    )
    keywords = models.ManyToManyField(Keyword, related_name="events")
    audience = models.ManyToManyField(
        Keyword, related_name="audience_events", blank=True
    )

    # this field is redundant, but allows to avoid expensive joins when
    # searching for local events
    local = models.BooleanField(default=False)

    # these fields are populated and kept up to date by the db. See migration 0080
    search_vector_fi = SearchVectorField(null=True)
    search_vector_en = SearchVectorField(null=True)
    search_vector_sv = SearchVectorField(null=True)

    class Meta:
        verbose_name = _("event")
        verbose_name_plural = _("events")

    class MPTTMeta:
        parent_attr = "super_event"

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._has_circular_replacement():
            raise ValidationError(
                _(
                    "Trying to replace this event with an event that is replaced by this event. "  # noqa: E501
                    "Please refrain from creating circular replacements and "
                    "remove one of the replacements."
                )
            )

        if self.replaced_by and not self.deleted:
            self.deleted = True
            logger.warning(
                "Event replaced without soft deleting. Soft deleting automatically",
                extra={"event": self},
            )

        # needed to cache location event numbers
        old_location = None

        # needed for notifications
        old_event_status = None
        old_publication_status = None
        old_deleted = None
        created = True

        if self.id:
            try:
                event = Event.objects.get(id=self.id)
                created = False
                old_location = event.location
                old_publication_status = event.publication_status
                old_event_status = event.event_status
                old_deleted = event.deleted
            except Event.DoesNotExist:
                pass

        # drafts may not have times set, so check that first
        start = getattr(self, "start_time", None)
        end = getattr(self, "end_time", None)
        if start and end:
            if start > end:
                raise ValidationError(
                    {
                        "end_time": _(
                            "The event end time cannot be earlier than the start time."
                        )
                    }
                )

        event_cancelled = (
            old_event_status != self.event_status
            and self.event_status == Event.Status.CANCELLED
        )
        event_deleted = old_deleted is False and self.deleted is True

        registration_to_cancel = None
        if (
            (event_deleted or event_cancelled)
            and (registration_to_cancel := getattr(self, "registration", None))
            and registration_to_cancel.has_payments
        ):
            raise ValidationError(
                _(
                    "Trying to cancel an event with paid signups. "
                    "Please cancel the signups first before cancelling the event."
                )
            )

        super().save(*args, **kwargs)

        # needed to cache location event numbers
        if not old_location and self.location:
            Place.objects.filter(id=self.location.id).update(n_events_changed=True)
        if old_location and not self.location:
            # drafts (or imported events) may not always have location set
            Place.objects.filter(id=old_location.id).update(n_events_changed=True)
        if old_location and self.location and old_location != self.location:
            Place.objects.filter(id__in=(old_location.id, self.location.id)).update(
                n_events_changed=True
            )

        # send notifications
        if (
            old_publication_status == PublicationStatus.DRAFT
            and self.publication_status == PublicationStatus.PUBLIC
        ):
            self.send_published_notification()
        if self.publication_status == PublicationStatus.DRAFT and event_deleted:
            self.send_deleted_notification()
        if (
            created
            and self.publication_status == PublicationStatus.DRAFT
            and not self.is_created_with_apikey
            # Only send super event notification to avoid spamming from
            # child events when recurring event.
            and not (self.super_event and self.super_event.is_recurring_super_event)
            # Do not send draft emails from events created by admins.
            and not self.publisher.admin_users.filter(id=self.created_by_id).exists()
        ):
            self.send_draft_posted_notification()

        if event_deleted or event_cancelled:
            # If there weren't any Talpa payments, cancel the registration or notify the
            # contact persons in the event transaction so that all changes can be reverted  # noqa: E501
            # in case of an exception.
            self.cancel_registration_signups_or_notify_contact_person(
                registration_to_cancel
            )

    def cancel_registration_signups_or_notify_contact_person(self, registration=None):
        if registration:
            registration.cancel_signups(is_event_cancellation=True)
        elif (
            self.super_event_id is not None
            and self.super_event.is_recurring_super_event
            and (registration := getattr(self.super_event, "registration", None))
        ):
            registration.send_event_cancellation_notifications(
                is_sub_event_cancellation=True
            )

    def __str__(self):
        name = ""
        languages = [lang[0] for lang in settings.LANGUAGES]
        for lang in languages:
            lang = lang.replace("-", "_")  # to handle complex codes like e.g. zh-hans
            s = getattr(self, "name_%s" % lang, None)
            if s:
                name = s
                break
        val = [name, "(%s)" % self.id]
        dcount = self.get_descendant_count()
        if dcount > 0:
            val.append(" (%d children)" % dcount)
        else:
            val.append(str(self.start_time))
        return " ".join(val)

    def is_admin(self, user):
        if user.is_superuser:
            return True
        else:
            return user.is_admin_of(self.publisher)

    def can_be_edited_by(self, user):
        """Check if current event can be edited by the given user"""
        if user.is_superuser:
            return True
        return user.can_edit_event(self.publisher, self.publication_status)

    def soft_delete(self, using=None):
        db_event = Event.objects.get(id=self.id)
        if db_event.deleted:
            return

        self.deleted = True
        self.save(
            update_fields=(
                "deleted",
                "last_modified_time",
            ),
            using=using,
            force_update=True,
        )

    def undelete(self, using=None):
        db_event = Event.objects.get(id=self.id)
        if not db_event.deleted:
            return

        self.deleted = False
        self.save(
            update_fields=(
                "deleted",
                "last_modified_time",
            ),
            using=using,
            force_update=True,
        )

    def _send_notification(self, notification_type, recipient_list, request=None):
        if len(recipient_list) == 0:
            logger.warning(
                "No recipients for notification type '%s'" % notification_type,
                extra={"event": self},
            )
            return

        context = {"event": self}

        try:
            rendered_notification = render_notification_template(
                notification_type, context
            )
        except NotificationTemplateException as e:
            logger.error(e, exc_info=True, extra={"request": request})
            return

        send_mail(
            rendered_notification["subject"],
            rendered_notification["body"],
            get_email_noreply_address(),
            recipient_list,
            html_message=rendered_notification["html_body"],
        )

    def _get_author_emails(self):
        author_emails = []
        author = self.created_by
        if author and author.email:
            author_emails.append(author.email)
        return author_emails

    def send_deleted_notification(self, request=None):
        recipient_list = self._get_author_emails()
        self._send_notification(
            NotificationType.UNPUBLISHED_EVENT_DELETED, recipient_list, request
        )

    def send_published_notification(self, request=None):
        recipient_list = self._get_author_emails()
        self._send_notification(
            NotificationType.EVENT_PUBLISHED, recipient_list, request
        )

    def send_draft_posted_notification(self, request=None):
        recipient_list = []
        for admin in self.publisher.admin_users.all():
            if admin.email:
                recipient_list.append(admin.email)
        self._send_notification(NotificationType.DRAFT_POSTED, recipient_list, request)

    @property
    def is_created_with_apikey(self) -> bool:
        from events.auth import ApiKeyUser

        try:
            if self.created_by and self.created_by.apikeyuser:
                return True
        except ApiKeyUser.DoesNotExist:
            pass
        return False

    @property
    def is_recurring_super_event(self) -> bool:
        return self.super_event_type == Event.SuperEventType.RECURRING

    def get_start_and_end_time_display(self, lang="fi", date_only=False) -> str:
        if date_only:
            formatter_func = format_date
        else:
            formatter_func = format_datetime

        if self.start_time and self.end_time:
            return (
                f"{formatter_func(self.start_time, lang)}"
                if self.start_time.date() == self.end_time.date() and date_only
                else f"{formatter_func(self.start_time, lang)} - {formatter_func(self.end_time, lang)}"  # noqa: E501
            )
        elif self.start_time:
            return f"{formatter_func(self.start_time, lang)} -"
        elif self.end_time:
            return f"- {formatter_func(self.end_time, lang)}"

        return ""


reversion.register(Event)


class EventFullText(models.Model):
    """
    A representation of the materialized view used in full-text search.
    """

    event = models.OneToOneField(
        Event,
        related_name="full_text",
        on_delete=models.DO_NOTHING,
        primary_key=True,
    )
    place = models.ForeignKey(
        Event, related_name="full_text_place", on_delete=models.DO_NOTHING
    )

    event_last_modified_time = models.DateTimeField()
    place_last_modified_time = models.DateTimeField()

    search_vector_fi = SearchVectorField()
    search_vector_en = SearchVectorField()
    search_vector_sv = SearchVectorField()

    class Meta:
        managed = False


@receiver(m2m_changed, sender=Event.keywords.through)
@receiver(m2m_changed, sender=Event.audience.through)
def keyword_added_or_removed(
    sender, model=None, instance=None, pk_set=None, action=None, **kwargs
):
    """
    Listens to event-keyword add signals to keep event number up to date
    """
    if action in ("post_add", "post_remove"):
        if model is Keyword:
            Keyword.objects.filter(pk__in=pk_set).update(n_events_changed=True)
        if model is Event:
            instance.n_events_changed = True
            instance.save(
                update_fields=("n_events_changed",), skip_last_modified_time=True
            )


class Offer(SimpleValueMixin, TranslatableSerializableMixin):
    serialize_fields = [{"name": "price"}, {"name": "description"}]

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, db_index=True, related_name="offers"
    )
    price = models.CharField(verbose_name=_("Price"), blank=True, max_length=1000)
    info_url = models.URLField(
        verbose_name=_("Web link to offer"), blank=True, null=True, max_length=1000
    )
    description = models.TextField(
        verbose_name=_("Offer description"), blank=True, null=True
    )
    # Don't expose is_free as an API field. It is used to distinguish
    # between missing price info and confirmed free entry.
    is_free = models.BooleanField(verbose_name=_("Is free"), default=False)

    price_groups = models.ManyToManyField(
        "registrations.PriceGroup",
        related_name="offers",
        blank=True,
        through="registrations.OfferPriceGroup",
        through_fields=("offer", "price_group"),
    )

    def value_fields(self):
        return ["price", "info_url", "description", "is_free"]


reversion.register(Offer)


class EventLink(models.Model, SimpleValueMixin):
    name = models.CharField(verbose_name=_("Name"), max_length=100, blank=True)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, db_index=True, related_name="external_links"
    )
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    link = models.URLField()

    class Meta:
        unique_together = (("name", "event", "language", "link"),)

    def value_fields(self):
        return ["name", "language_id", "link"]


class Video(SimpleValueMixin, TranslatableSerializableMixin):
    serialize_fields = [{"name": "name"}, {"name": "url"}, {"name": "alt_text"}]

    name = models.CharField(
        verbose_name=_("Name"), max_length=255, db_index=True, default=""
    )
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, db_index=True, related_name="videos"
    )
    url = models.URLField()
    alt_text = models.CharField(
        verbose_name=_("Alt text"), max_length=320, null=True, blank=True
    )

    class Meta:
        unique_together = (("name", "event", "url"),)

    def value_fields(self):
        return ["name", "url"]


class ExportInfo(models.Model):
    target_id = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    target_system = models.CharField(
        max_length=255, db_index=True, null=True, blank=True
    )
    last_exported_time = models.DateTimeField(null=True, blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50)
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        unique_together = (("target_system", "content_type", "object_id"),)

    def save(self, *args, **kwargs):
        self.last_exported_time = BaseModel.now()
        super().save(*args, **kwargs)


class EventAggregate(models.Model):
    super_event = models.OneToOneField(
        Event, on_delete=models.CASCADE, related_name="aggregate", null=True
    )


class EventAggregateMember(models.Model):
    event_aggregate = models.ForeignKey(
        EventAggregate, on_delete=models.CASCADE, related_name="members"
    )
    event = models.OneToOneField(Event, on_delete=models.CASCADE)


class Feedback(models.Model):
    name = models.CharField(verbose_name=_("Name"), max_length=255, blank=True)
    email = models.EmailField(verbose_name=_("E-mail"))
    subject = models.CharField(verbose_name=_("Subject"), max_length=255, blank=True)
    body = models.TextField(verbose_name=_("Body"), max_length=10000, blank=True)

    def save(self, *args, **kwargs):
        send_mail(
            subject=f"[LinkedEvents] {self.subject} reported by {self.name}",
            message=f"Email: {self.email}, message: {self.body}",
            from_email=get_email_noreply_address(),
            recipient_list=[settings.SUPPORT_EMAIL],
            fail_silently=False,
        )

        super().save(*args, **kwargs)
