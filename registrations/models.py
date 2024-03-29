import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import DateTimeField, ExpressionWrapper, F, Sum, UniqueConstraint
from django.forms.fields import MultipleChoiceField
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.functional import cached_property
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from django_orghierarchy.models import Organization
from encrypted_fields import fields
from helsinki_gdpr.models import SerializableMixin

from events.models import Event, Language, Offer
from registrations.enums import VatPercentage
from registrations.exceptions import PriceGroupValidationError
from registrations.notifications import (
    get_registration_user_access_invitation_subject,
    get_registration_user_access_invitation_texts,
    get_registration_user_access_invitation_variables,
    get_signup_notification_subject,
    get_signup_notification_texts,
    get_signup_notification_variables,
    NOTIFICATION_TYPES,
    NotificationType,
    SignUpNotificationType,
)
from registrations.utils import (
    code_validity_duration,
    create_event_ics_file_content,
    create_or_update_web_store_merchant,
    create_web_store_api_order,
    get_email_noreply_address,
    get_ui_locales,
    strip_trailing_zeroes_from_decimal,
)

User = settings.AUTH_USER_MODEL

logger = logging.getLogger(__name__)
anonymize_replacement = "<DELETED>"

VAT_PERCENTAGES = (
    (VatPercentage.VAT_24.value, "24 %"),
    (VatPercentage.VAT_14.value, "14 %"),
    (VatPercentage.VAT_10.value, "10 %"),
    (VatPercentage.VAT_0.value, "0 %"),
)


class MandatoryFields(models.TextChoices):
    """Choices for mandatory fields on SignUp model."""

    CITY = "city", _("City")
    FIRST_NAME = "first_name", _("First name")
    LAST_NAME = "last_name", _("Last name")
    PHONE_NUMBER = "phone_number", _("Phone number")
    STREET_ADDRESS = "street_address", _("Street address")
    ZIPCODE = "zipcode", _("ZIP code")


# https://gist.github.com/danni/f55c4ce19598b2b345ef?permalink_comment_id=4448023#gistcomment-4448023
class _MultipleChoiceField(MultipleChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs.pop("base_field", None)
        kwargs.pop("max_length", None)
        super().__init__(*args, **kwargs)


# https://gist.github.com/danni/f55c4ce19598b2b345ef?permalink_comment_id=4448023#gistcomment-4448023
class ChoiceArrayField(ArrayField):
    """
    A field that allows to store an array of choices.

    Uses Django postgres ArrayField
    and a _MultipleChoiceField for its formfield.
    """

    def formfield(self, **kwargs):
        return super().formfield(
            **{
                "form_class": _MultipleChoiceField,
                "choices": self.base_field.choices,
                **kwargs,
            }
        )


class SignUpOrGroupDependingMixin:
    @cached_property
    def signup_or_signup_group(self):
        return getattr(self, "signup_group", None) or getattr(self, "signup", None)

    def save(self, *args, **kwargs):
        if not (self.signup_group_id or self.signup_id):
            raise ValidationError(_("You must provide either signup_group or signup."))

        if self.signup_group_id and self.signup_id:
            raise ValidationError(
                _("You can only provide signup_group or signup, not both.")
            )

        super().save(*args, **kwargs)


class ObjectsWithoutSoftDeletedManager(SerializableMixin.SerializableManager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted=False)


class SoftDeletableBaseModel(models.Model):
    deleted = models.BooleanField(default=False)

    objects = ObjectsWithoutSoftDeletedManager()
    all_objects = models.Manager()

    def soft_delete(self):
        self.deleted = True

        update_fields = ["deleted"]
        for field in ("last_modified_time", "last_modified_by"):
            if hasattr(self, field):
                update_fields.append(field)

        self.save(update_fields=update_fields)

    def undelete(self):
        self.deleted = False

        update_fields = ["deleted"]
        for field in ("last_modified_time", "last_modified_by"):
            if hasattr(self, field):
                update_fields.append(field)

        self.save(update_fields=update_fields)

    class Meta:
        abstract = True


class CreatedModifiedBaseModel(models.Model):
    created_time = models.DateTimeField(
        verbose_name=_("Created at"),
        null=False,
        blank=True,
        auto_now_add=True,
    )
    last_modified_time = models.DateTimeField(
        verbose_name=_("Modified at"),
        null=False,
        blank=True,
        auto_now=True,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created_by",
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_last_modified_by",
    )

    class Meta:
        abstract = True


class WebStoreMerchant(CreatedModifiedBaseModel):
    organization = models.ForeignKey(
        Organization,
        related_name="web_store_merchants",
        on_delete=models.CASCADE,
    )

    # Since merchants cannot be deleted from Talpa, allow to
    # toggle their active / inactive status instead in Linked Events.
    active = models.BooleanField(
        verbose_name=_("Is active"),
        default=True,
    )

    name = models.CharField(
        verbose_name=_("Name"),
        max_length=100,
    )
    street_address = models.CharField(
        verbose_name=_("Street address"),
        max_length=500,
    )
    zipcode = models.CharField(
        verbose_name=_("ZIP code"),
        max_length=10,
    )
    city = models.CharField(
        verbose_name=_("City"),
        max_length=50,
    )
    email = models.EmailField(verbose_name=_("E-mail"))
    phone_number = models.CharField(
        verbose_name=_("Phone number"),
        max_length=18,
    )
    url = models.URLField(verbose_name=_("URL"))
    terms_of_service_url = models.URLField(verbose_name=_("Terms of Service URL"))
    business_id = models.CharField(
        verbose_name=_("Business ID"),
        max_length=9,
    )

    # Paytrail "main" merchant ID. 100 character limit is an estimated maximum provided
    # by the Talpa team. Real values are probably much shorter.
    paytrail_merchant_id = models.CharField(
        verbose_name=_("Paytrail merchant ID"),
        max_length=100,
    )

    # Talpa merchant ID.
    merchant_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
    )

    def to_web_store_merchant_json(self):
        return {
            "merchantName": self.name,
            "merchantStreet": self.street_address,
            "merchantZip": self.zipcode,
            "merchantCity": self.city,
            "merchantEmail": self.email,
            "merchantPhone": self.phone_number,
            "merchantUrl": self.url,
            "merchantTermsOfServiceUrl": self.terms_of_service_url,
            "merchantBusinessId": self.business_id,
            "merchantPaytrailMerchantId": self.paytrail_merchant_id,
            "merchantShopId": self.paytrail_merchant_id,
        }

    def delete(self, using=None, keep_parents=False, force_delete=False):
        if force_delete:
            pk = self.pk
            super().delete()
            logger.info(f"Deleted Talpa merchant {self.name} (ID: {pk})")
        else:
            raise ValidationError(_("Cannot delete a Talpa merchant."))

    @transaction.atomic
    def save(self, *args, **kwargs):
        created = self.pk is None

        super().save(*args, **kwargs)

        if (
            not settings.WEB_STORE_INTEGRATION_ENABLED
            or not self.active
            or kwargs.get("update_fields") == {"merchant_id"}
        ):
            return

        create_or_update_web_store_merchant(self, created)


class PriceGroup(CreatedModifiedBaseModel):
    """Price group / pricing category that is selectable when creating a registration. These can be
    created and managed by admins for publishers / organizations. Default price groups do not have a
    publisher, but are system-wide default groups.
    """

    publisher = models.ForeignKey(
        "django_orghierarchy.Organization",
        on_delete=models.CASCADE,
        verbose_name=_("Publisher"),
        related_name="registration_price_groups",
        null=True,
        blank=False,
    )

    description = models.CharField(max_length=255)

    is_free = models.BooleanField(default=False)

    @property
    def old_instance(self):
        if not self.pk:
            return None

        return PriceGroup.objects.get(pk=self.pk)

    @property
    def publisher_is_valid(self):
        if not self.old_instance:
            return True

        return (
            self.old_instance.publisher_id == self.publisher_id
            or not self.registration_price_groups.exists()
        )

    def delete(self, *args, **kwargs):
        if self.old_instance and not self.old_instance.publisher_id:
            raise PriceGroupValidationError(
                _("You may not delete a default price group.")
            )

        super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.old_instance and not self.old_instance.publisher_id:
            raise PriceGroupValidationError(
                _("You may not edit a default price group.")
            )

        if not self.publisher_is_valid:
            raise PriceGroupValidationError(
                _(
                    "You may not change the publisher of a price group that has been used "
                    "in registrations."
                )
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.description


class Registration(CreatedModifiedBaseModel):
    event = models.OneToOneField(
        Event,
        on_delete=models.CASCADE,
        related_name="registration",
        null=False,
        blank=True,
    )
    attendee_registration = models.BooleanField(default=False, null=False)
    audience_min_age = models.PositiveSmallIntegerField(
        verbose_name=_("Minimum recommended age"), blank=True, null=True, db_index=True
    )
    audience_max_age = models.PositiveSmallIntegerField(
        verbose_name=_("Maximum recommended age"), blank=True, null=True, db_index=True
    )

    enrolment_start_time = models.DateTimeField(
        verbose_name=_("Enrollment start time"), blank=True, null=True
    )
    enrolment_end_time = models.DateTimeField(
        verbose_name=_("Enrollment end time"), blank=True, null=True
    )

    confirmation_message = models.TextField(
        verbose_name=_("Confirmation message"), blank=True, null=True
    )
    instructions = models.TextField(
        verbose_name=_("Instructions"), blank=True, null=True
    )

    maximum_attendee_capacity = models.PositiveSmallIntegerField(
        verbose_name=_("Maximum attendee capacity"), null=True, blank=True
    )
    minimum_attendee_capacity = models.PositiveSmallIntegerField(
        verbose_name=_("Minimum attendee capacity"), null=True, blank=True
    )
    waiting_list_capacity = models.PositiveSmallIntegerField(
        verbose_name=_("Waiting list capacity"), null=True, blank=True
    )
    maximum_group_size = models.PositiveSmallIntegerField(
        verbose_name=_("Maximum group size"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )

    mandatory_fields = ChoiceArrayField(
        models.CharField(
            max_length=16,
            choices=MandatoryFields.choices,
            blank=True,
        ),
        default=list,
        blank=True,
        verbose_name=_("Mandatory fields"),
    )

    price_groups = models.ManyToManyField(
        PriceGroup,
        related_name="registrations",
        blank=True,
        through="RegistrationPriceGroup",
        through_fields=("registration", "price_group"),
    )

    remaining_attendee_capacity = models.PositiveSmallIntegerField(
        blank=True, null=True, default=None
    )
    remaining_waiting_list_capacity = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        default=None,
    )

    @property
    def data_source(self):
        return self.event.data_source

    @property
    def publisher(self):
        return self.event.publisher

    @cached_property
    def reserved_seats_amount(self):
        return (
            # Calculate expiration time for each reservation
            self.reservations.annotate(
                expires_at=ExpressionWrapper(
                    F("timestamp")
                    + timedelta(minutes=1) * code_validity_duration(F("seats")),
                    output_field=DateTimeField(),
                )
            )
            # Filter to get all not expired reservations
            .filter(expires_at__gte=localtime())
            # Sum  seats of not expired reservation
            .aggregate(seats_sum=Sum("seats", output_field=models.IntegerField()))[
                "seats_sum"
            ]
            or 0
        )

    @cached_property
    def current_attendee_count(self):
        return self.signups.filter(
            attendee_status=SignUp.AttendeeStatus.ATTENDING
        ).count()

    @cached_property
    def current_waiting_list_count(self):
        return self.signups.filter(
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST
        ).count()

    def calculate_remaining_attendee_capacity(self):
        maximum_attendee_capacity = self.maximum_attendee_capacity

        if maximum_attendee_capacity is None:
            return None

        attendee_count = self.current_attendee_count
        reserved_seats_amount = self.reserved_seats_amount

        return max(
            maximum_attendee_capacity - attendee_count - reserved_seats_amount, 0
        )

    def calculate_remaining_waiting_list_capacity(self):
        waiting_list_capacity = self.waiting_list_capacity

        if waiting_list_capacity is None:
            return None

        waiting_list_count = self.current_waiting_list_count
        reserved_seats_amount = self.reserved_seats_amount
        maximum_attendee_capacity = self.maximum_attendee_capacity

        if maximum_attendee_capacity is not None:
            # Calculate the amount of reserved seats that are used for actual seats
            # and reduce it from reserved_seats_amount to get amount of reserved seats
            # in the waiting list
            attendee_count = self.current_attendee_count
            reserved_seats_amount = max(
                reserved_seats_amount
                - max(maximum_attendee_capacity - attendee_count, 0),
                0,
            )

        return max(
            waiting_list_capacity - waiting_list_count - reserved_seats_amount, 0
        )

    def get_first_waitlisted(self):
        waitlisted = (
            self.signups.filter(attendee_status=SignUp.AttendeeStatus.WAITING_LIST)
            .select_for_update()
            .order_by("id")
        )

        return waitlisted[0] if waitlisted else None

    def move_first_waitlisted_to_attending_with_payment_link(self):
        first_on_list = self.get_first_waitlisted()
        if not first_on_list:
            return

        try:
            payment = (
                first_on_list.create_web_store_payment()
                if first_on_list.price_group.price > 0
                else None
            )
        except (ValidationError, AttributeError) as exc:
            logger.error(
                f"Failed to create payment when moving waitlisted signup #{first_on_list.pk} "
                f"to attending: {exc}"
            )
            return

        if not payment:
            self.move_first_waitlisted_to_attending(first_on_list)
        else:
            contact_person = first_on_list.actual_contact_person
            contact_person.send_notification(
                SignUpNotificationType.TRANSFER_AS_PARTICIPANT_WITH_PAYMENT,
                payment_link=payment.checkout_url,
            )

    def move_first_waitlisted_to_attending(self, first_on_list=None):
        first_on_list = first_on_list or self.get_first_waitlisted()
        if not first_on_list:
            return

        first_on_list.attendee_status = SignUp.AttendeeStatus.ATTENDING
        first_on_list.save(update_fields=["attendee_status"])

        contact_person = first_on_list.actual_contact_person
        if contact_person:
            contact_person.send_notification(
                SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT
            )

    def can_be_edited_by(self, user):
        """Check if current registration can be edited by the given user"""
        return (
            user.is_superuser
            or user.is_admin_of(self.publisher)
            or user.is_registration_admin_of(self.publisher)
            or user.is_substitute_user_of(self.registration_user_accesses)
        )


class RegistrationPriceGroupBaseModel(models.Model):
    price = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    price_without_vat = models.DecimalField(
        max_digits=19, decimal_places=2, default=Decimal("0")
    )
    vat_percentage = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        choices=VAT_PERCENTAGES,
        default=VatPercentage.VAT_0.value,
    )
    vat = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))

    def calculate_vat_and_price_without_vat(self):
        cents = Decimal(".01")

        self.price_without_vat = (
            self.price / (1 + self.vat_percentage / 100)
        ).quantize(cents, ROUND_HALF_UP)

        self.vat = (self.price - self.price_without_vat).quantize(cents, ROUND_HALF_UP)

    def save(self, *args, **kwargs):
        self.calculate_vat_and_price_without_vat()

        if update_fields := kwargs.get("update_fields"):
            updated_update_fields = set(update_fields)
            updated_update_fields.update({"vat", "price_without_vat"})
            kwargs["update_fields"] = updated_update_fields

        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class OfferPriceGroup(RegistrationPriceGroupBaseModel):
    """Price group selections for event Offers. These will be the initial values for
    registration price groups."""

    offer = models.ForeignKey(
        Offer,
        related_name="offer_price_groups",
        on_delete=models.CASCADE,
    )

    price_group = models.ForeignKey(
        PriceGroup,
        related_name="offer_price_groups",
        on_delete=models.PROTECT,
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["offer", "price_group"],
                name="unique_offer_price_group",
            ),
        ]


class RegistrationPriceGroup(RegistrationPriceGroupBaseModel):
    """Price group selections for SignUps (= what the end-user doing a signup can choose from)."""

    registration = models.ForeignKey(
        Registration,
        related_name="registration_price_groups",
        on_delete=models.CASCADE,
    )

    price_group = models.ForeignKey(
        PriceGroup,
        related_name="registration_price_groups",
        on_delete=models.PROTECT,
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["registration", "price_group"],
                name="unique_registration_price_group",
            ),
        ]


class SignUpMixin:
    @cached_property
    def extra_info(self):
        protected_data = getattr(self, "protected_data", None)
        return getattr(protected_data, "extra_info", None)

    @property
    def data_source(self):
        return self.registration.data_source

    @property
    def publisher(self):
        return self.registration.publisher

    @cached_property
    def actual_contact_person(self):
        if signup_group := getattr(self, "signup_group", None):
            return getattr(signup_group, "contact_person", None)

        return getattr(self, "contact_person", None)

    def can_be_edited_by(self, user):
        """Check if the current signup can be edited by the given user"""
        return (
            user.is_superuser
            or user.is_registration_admin_of(self.publisher)
            or (
                user.is_admin_of(self.publisher)
                and self.registration.created_by_id == user.id
            )
            or user.is_substitute_user_of(self.registration.registration_user_accesses)
            or user.is_registration_user_access_user_of(
                self.registration.registration_user_accesses
            )
            or user.id == self.created_by_id
            or user.is_contact_person_of(self)
        )

    def can_be_deleted_by(self, user):
        """Check if current signup can be deleted by the given user"""
        return (
            user.is_superuser
            or user.is_registration_admin_of(self.publisher)
            or (
                user.is_admin_of(self.publisher)
                and self.registration.created_by_id == user.id
            )
            or user.is_substitute_user_of(self.registration.registration_user_accesses)
            or user.id == self.created_by_id
            or user.is_contact_person_of(self)
        )

    def is_user_editable_resources(self):
        return bool(self.data_source and self.data_source.user_editable_resources)

    def create_web_store_payment(self):
        if isinstance(self, SignUp):
            kwargs = {"signup": self}
        else:
            kwargs = {"signup_group": self}

        kwargs["expires_at"] = localtime() + timedelta(
            hours=settings.WEB_STORE_ORDER_EXPIRATION_HOURS
        )

        api_response = create_web_store_api_order(self, kwargs["expires_at"])

        if api_response.get("orderId"):
            kwargs["external_order_id"] = api_response["orderId"]

        if api_response.get("priceTotal"):
            kwargs["amount"] = Decimal(api_response["priceTotal"])
        else:
            kwargs["amount"] = self.total_payment_amount

        if api_response.get("checkoutUrl"):
            kwargs["checkout_url"] = api_response["checkoutUrl"]

        if api_response.get("loggedInCheckoutUrl"):
            kwargs["logged_in_checkout_url"] = api_response["loggedInCheckoutUrl"]

        kwargs["created_by"] = self.created_by
        kwargs["last_modified_by"] = self.created_by

        return SignUpPayment.objects.create(**kwargs)

    @property
    def web_store_meta_label(self):
        raise NotImplementedError("web_store_meta_label not implemented")

    @staticmethod
    def add_price_group_to_web_store_order_data(price_group, order_data):
        order_data["items"].append(price_group.to_web_store_order_json())

        order_data["priceNet"] += price_group.price_without_vat
        order_data["priceVat"] += price_group.vat
        order_data["priceTotal"] += price_group.price

    def add_price_groups_to_web_store_order_data(self, order_data):
        raise NotImplementedError(
            "add_price_groups_to_web_store_order_data not implemented"
        )

    def to_web_store_order_json(self, user_uuid: UUID, contact_person=None):
        order_data = {
            "namespace": settings.WEB_STORE_API_NAMESPACE,
            "user": str(user_uuid),
            "items": [],
            "priceNet": Decimal("0"),
            "priceVat": Decimal("0"),
            "priceTotal": Decimal("0"),
        }

        contact_person = contact_person or getattr(self, "contact_person", None)
        if contact_person:
            order_data["customer"] = contact_person.to_web_store_order_json()

        order_data["language"] = getattr(contact_person, "service_language_id", "fi")

        self.add_price_groups_to_web_store_order_data(order_data)
        order_data["priceNet"] = str(
            strip_trailing_zeroes_from_decimal(order_data["priceNet"])
        )
        order_data["priceVat"] = str(
            strip_trailing_zeroes_from_decimal(order_data["priceVat"])
        )
        order_data["priceTotal"] = str(
            strip_trailing_zeroes_from_decimal(order_data["priceTotal"])
        )

        if order_data["items"]:
            order_data["items"][len(order_data["items"]) - 1]["meta"] = [
                {
                    "key": "eventName",
                    "value": self.registration.event.name,
                    "label": str(self.web_store_meta_label),
                    "visibleInCheckout": True,
                    "ordinal": "0",
                }
            ]

        return order_data


class SignUpGroup(
    CreatedModifiedBaseModel, SoftDeletableBaseModel, SignUpMixin, SerializableMixin
):
    registration = models.ForeignKey(
        Registration, on_delete=models.PROTECT, related_name="signup_groups"
    )
    anonymization_time = models.DateTimeField(
        verbose_name=_("Anonymization time"),
        null=True,
        editable=False,
    )

    serialize_fields = (
        {"name": "id"},
        {"name": "registration_id"},
        {"name": "extra_info"},
        {"name": "signups_count"},
        {"name": "contact_person"},
    )

    @transaction.atomic
    def soft_delete(self):
        super().soft_delete()

        for signup in SignUp.objects.filter(signup_group_id=self.pk):
            signup.last_modified_by = self.last_modified_by
            signup.soft_delete()

        SignUpContactPerson.objects.filter(signup_group_id=self.pk).update(deleted=True)
        SignUpGroupProtectedData.objects.filter(signup_group_id=self.pk).update(
            deleted=True
        )
        SignUpPayment.objects.filter(signup_group_id=self.pk).update(
            deleted=True,
            last_modified_by=self.last_modified_by,
            last_modified_time=self.last_modified_time,
        )

    @transaction.atomic
    def undelete(self):
        super().undelete()

        for signup in SignUp.all_objects.filter(signup_group_id=self.pk):
            signup.last_modified_by = self.last_modified_by
            signup.undelete()

        SignUpContactPerson.all_objects.filter(signup_group_id=self.pk).update(
            deleted=False
        )
        SignUpGroupProtectedData.all_objects.filter(signup_group_id=self.pk).update(
            deleted=False
        )
        SignUpPayment.all_objects.filter(signup_group_id=self.pk).update(
            deleted=False,
            last_modified_by=self.last_modified_by,
            last_modified_time=self.last_modified_time,
        )

    @cached_property
    def signups_count(self):
        return self.signups.count()

    @cached_property
    def attending_signups(self):
        return self.signups.filter(attendee_status=SignUp.AttendeeStatus.ATTENDING)

    @cached_property
    def total_payment_amount(self):
        total_payment_amount = Decimal("0")

        for signup in self.signups.select_related("price_group").filter(
            price_group__isnull=False
        ):
            total_payment_amount += signup.total_payment_amount

        return total_payment_amount

    @transaction.atomic
    def anonymize(self):
        # Allow to anonymize signup only once
        if self.anonymization_time is None:
            if contact_person := getattr(self, "contact_person", None):
                contact_person.anonymize()

            if protected_data := getattr(self, "protected_data", None):
                protected_data.anonymize()

            # Anonymize all the signups of the group
            signups = self.signups.all()

            for signup in signups:
                signup.anonymize()

            self.anonymization_time = localtime()
            self.created_by = None
            self.last_modified_by = None
            self.save()

    @property
    def web_store_meta_label(self):
        labels = {
            Event.TypeId.GENERAL: _("Group registration to event"),
            Event.TypeId.COURSE: _("Group registration to course"),
            Event.TypeId.VOLUNTEERING: _("Group registration to volunteering"),
        }

        return labels[self.registration.event.type_id]

    def add_price_groups_to_web_store_order_data(self, order_data):
        signups_with_price_groups = (
            self.signups.select_related("price_group")
            .filter(price_group__isnull=False)
            .order_by("pk")
        )
        if not signups_with_price_groups.exists():
            raise PriceGroupValidationError(
                _("No price groups exist for signup group.")
            )

        for signup in signups_with_price_groups:
            signup_price_group = getattr(signup, "price_group", None)
            self.add_price_group_to_web_store_order_data(signup_price_group, order_data)


class SignUpProtectedDataBaseModel(models.Model):
    registration = models.ForeignKey(
        Registration, on_delete=models.PROTECT, related_name="%(class)s"
    )

    extra_info = fields.EncryptedTextField(
        verbose_name=_("Extra info"),
        blank=True,
        null=True,
        default=None,
    )

    def anonymize(self):
        self.extra_info = None
        self.save()

    class Meta:
        abstract = True


class SignUpGroupProtectedData(SignUpProtectedDataBaseModel, SoftDeletableBaseModel):
    signup_group = models.OneToOneField(
        SignUpGroup,
        related_name="protected_data",
        null=True,
        default=None,
        on_delete=models.SET_NULL,
    )


class RegistrationUserAccess(models.Model):
    email = models.EmailField(verbose_name=_("E-mail"))

    registration = models.ForeignKey(
        Registration,
        on_delete=models.CASCADE,
        related_name="registration_user_accesses",
    )

    language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registration_user_access_language",
    )

    is_substitute_user = models.BooleanField(default=False)

    def can_be_edited_by(self, user):
        """Check if current registration user can be edited by the given user"""
        if user.is_superuser:
            return True
        return user.is_admin_of(self.registration.event.publisher)

    def get_language_pk(self):
        if self.language:
            return self.language.pk
        return "fi"

    def send_invitation(self):
        subject = get_registration_user_access_invitation_subject(self)

        invitation_template = "registration_user_access_invitation.html"
        email_variables = get_registration_user_access_invitation_variables(self)
        email_variables["texts"] = get_registration_user_access_invitation_texts(self)

        with translation.override(self.get_language_pk()):
            rendered_body = render_to_string(invitation_template, email_variables)

        send_mail(
            subject,
            rendered_body,
            get_email_noreply_address(),
            [self.email],
            html_message=rendered_body,
        )

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.pk:
            old_instance = RegistrationUserAccess.objects.filter(pk=self.pk).first()
        else:
            old_instance = None

        super().save(*args, **kwargs)

        if (
            not old_instance
            or old_instance.email != self.email
            or old_instance.is_substitute_user != self.is_substitute_user
        ):
            self.send_invitation()

    class Meta:
        unique_together = ("email", "registration")


class SignUp(
    CreatedModifiedBaseModel, SoftDeletableBaseModel, SignUpMixin, SerializableMixin
):
    class AttendeeStatus:
        WAITING_LIST = "waitlisted"
        ATTENDING = "attending"

    ATTENDEE_STATUSES = (
        (AttendeeStatus.WAITING_LIST, _("Waitlisted")),
        (AttendeeStatus.ATTENDING, _("Attending")),
    )

    class PresenceStatus:
        NOT_PRESENT = "not_present"
        PRESENT = "present"

    PRESENCE_STATUSES = (
        (PresenceStatus.NOT_PRESENT, _("Not present")),
        (PresenceStatus.PRESENT, _("Present")),
    )

    registration = models.ForeignKey(
        Registration, on_delete=models.PROTECT, related_name="signups"
    )

    signup_group = models.ForeignKey(
        SignUpGroup,
        on_delete=models.CASCADE,
        related_name="signups",
        blank=True,
        null=True,
    )

    first_name = models.CharField(
        verbose_name=_("First name"),
        max_length=50,
        blank=True,
        null=True,
        default=None,
    )
    last_name = models.CharField(
        verbose_name=_("Last name"),
        max_length=50,
        blank=True,
        null=True,
        default=None,
    )
    phone_number = models.CharField(
        verbose_name=_("Phone number"),
        max_length=18,
        blank=True,
        null=True,
        default=None,
    )
    city = models.CharField(
        verbose_name=_("City"),
        max_length=50,
        blank=True,
        null=True,
        default=None,
    )
    attendee_status = models.CharField(
        verbose_name=_("Attendee status"),
        max_length=25,
        choices=ATTENDEE_STATUSES,
        default=AttendeeStatus.ATTENDING,
        db_index=True,
    )
    street_address = models.CharField(
        verbose_name=_("Street address"),
        max_length=500,
        blank=True,
        null=True,
        default=None,
    )
    zipcode = models.CharField(
        verbose_name=_("ZIP code"),
        max_length=10,
        blank=True,
        null=True,
        default=None,
    )

    presence_status = models.CharField(
        verbose_name=_("Presence status"),
        max_length=25,
        choices=PRESENCE_STATUSES,
        default=PresenceStatus.NOT_PRESENT,
    )

    user_consent = models.BooleanField(
        verbose_name=_("User consent"),
        default=False,
    )

    anonymization_time = models.DateTimeField(
        verbose_name=_("Anonymization time"),
        null=True,
        editable=False,
    )

    serialize_fields = (
        {"name": "first_name"},
        {"name": "last_name"},
        {"name": "date_of_birth"},
        {"name": "phone_number"},
        {"name": "city"},
        {"name": "street_address"},
        {"name": "zipcode"},
        {"name": "registration_id"},
        {"name": "signup_group"},
        {"name": "extra_info"},
        {
            "name": "attendee_status",
            "accessor": lambda value: dict(SignUp.ATTENDEE_STATUSES).get(value, value),
        },
        {
            "name": "presence_status",
            "accessor": lambda value: dict(SignUp.PRESENCE_STATUSES).get(value, value),
        },
        {"name": "user_consent"},
        {"name": "contact_person"},
    )

    @transaction.atomic
    def soft_delete(self):
        super().soft_delete()

        SignUpContactPerson.objects.filter(signup_id=self.pk).update(deleted=True)
        SignUpProtectedData.objects.filter(signup_id=self.pk).update(deleted=True)
        SignUpPriceGroup.objects.filter(signup_id=self.pk).update(deleted=True)
        SignUpPayment.objects.filter(signup_id=self.pk).update(
            deleted=True,
            last_modified_by=self.last_modified_by,
            last_modified_time=self.last_modified_time,
        )

    @transaction.atomic
    def undelete(self):
        super().undelete()

        SignUpContactPerson.all_objects.filter(signup_id=self.pk).update(deleted=False)
        SignUpProtectedData.all_objects.filter(signup_id=self.pk).update(deleted=False)
        SignUpPriceGroup.all_objects.filter(signup_id=self.pk).update(deleted=False)
        SignUpPayment.all_objects.filter(signup_id=self.pk).update(
            deleted=False,
            last_modified_by=self.last_modified_by,
            last_modified_time=self.last_modified_time,
        )

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    @cached_property
    def date_of_birth(self):
        protected_data = getattr(self, "protected_data", None)
        return getattr(protected_data, "date_of_birth", None)

    @cached_property
    def total_payment_amount(self):
        price_group = getattr(self, "price_group", None)
        return price_group.price if price_group is not None else Decimal("0")

    @property
    def is_attending(self):
        return self.attendee_status == SignUp.AttendeeStatus.ATTENDING

    @transaction.atomic
    def anonymize(self):
        # Allow to anonymize signup group only once
        if self.anonymization_time is None:
            if contact_person := getattr(self, "contact_person", None):
                contact_person.anonymize()

            if protected_data := getattr(self, "protected_data", None):
                protected_data.anonymize()

            self.first_name = anonymize_replacement
            self.last_name = anonymize_replacement
            self.street_address = anonymize_replacement
            self.anonymization_time = localtime()
            self.created_by = None
            self.last_modified_by = None
            self.save()

    @property
    def web_store_meta_label(self):
        labels = {
            Event.TypeId.GENERAL: _("Registration to event"),
            Event.TypeId.COURSE: _("Registration to course"),
            Event.TypeId.VOLUNTEERING: _("Registration to volunteering"),
        }

        return labels[self.registration.event.type_id]

    def add_price_groups_to_web_store_order_data(self, order_data):
        signup_price_group = getattr(self, "price_group", None)
        if not signup_price_group:
            raise PriceGroupValidationError(_("Price group does not exist for signup."))

        self.add_price_group_to_web_store_order_data(signup_price_group, order_data)


class SignUpProtectedData(SignUpProtectedDataBaseModel, SoftDeletableBaseModel):
    date_of_birth = fields.EncryptedDateField(
        verbose_name=_("Date of birth"), blank=True, null=True
    )

    signup = models.OneToOneField(
        SignUp,
        related_name="protected_data",
        null=True,
        default=None,
        on_delete=models.SET_NULL,
    )


class SignUpContactPerson(
    SoftDeletableBaseModel, SignUpOrGroupDependingMixin, SerializableMixin
):
    # For signups that belong to a group.
    signup_group = models.OneToOneField(
        SignUpGroup,
        on_delete=models.CASCADE,
        related_name="contact_person",
        null=True,
        default=None,
    )

    # For signups that do not belong to a group.
    signup = models.OneToOneField(
        SignUp,
        on_delete=models.CASCADE,
        related_name="contact_person",
        null=True,
        default=None,
    )

    first_name = models.CharField(
        verbose_name=_("First name"),
        max_length=50,
        blank=True,
        null=True,
        default=None,
    )
    last_name = models.CharField(
        verbose_name=_("Last name"),
        max_length=50,
        blank=True,
        null=True,
        default=None,
    )

    email = models.EmailField(
        verbose_name=_("E-mail"), blank=True, null=True, default=None
    )

    phone_number = models.CharField(
        verbose_name=_("Phone number"),
        max_length=18,
        blank=True,
        null=True,
        default=None,
    )

    native_language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signup_contact_person_native_language",
    )
    service_language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signup_contact_person_service_language",
    )

    membership_number = models.CharField(
        verbose_name=_("Membership number"),
        max_length=50,
        blank=True,
        null=True,
        default=None,
    )

    notifications = models.CharField(
        verbose_name=_("Notification type"),
        max_length=25,
        choices=NOTIFICATION_TYPES,
        default=NotificationType.NO_NOTIFICATION,
    )

    access_code = models.CharField(
        _("Access code"),
        max_length=128,
        blank=True,
        null=True,
        default=None,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_persons",
    )

    serialize_fields = (
        {"name": "id"},
        {"name": "first_name"},
        {"name": "last_name"},
        {"name": "email"},
        {"name": "phone_number"},
        {"name": "native_language", "accessor": lambda value: str(value)},
        {"name": "service_language", "accessor": lambda value: str(value)},
        {"name": "membership_number"},
        {
            "name": "notifications",
            "accessor": lambda value: dict(NOTIFICATION_TYPES).get(value, value),
        },
    )

    def can_create_access_code(self, current_user: User) -> bool:
        if not self.email:
            return False

        if (
            self.email == current_user.email
            and self.signup_or_signup_group.can_be_edited_by(current_user)
            and self.signup_or_signup_group.can_be_deleted_by(current_user)
        ):
            # User already has full permissions for the signup or signup group.
            return False

        return True

    def create_access_code(self) -> str:
        access_code = str(uuid4())

        self.access_code = make_password(access_code)
        self.save(update_fields=["access_code"])

        return access_code

    def check_access_code(self, access_code: str) -> bool:
        if not (access_code and self.access_code) or self.user_id:
            return False

        return check_password(access_code, self.access_code)

    def link_user(self, user: User) -> None:
        self.access_code = None
        self.user = user
        self.save(update_fields=["access_code", "user"])

    @cached_property
    def registration(self):
        return self.signup_or_signup_group.registration

    def get_service_language_pk(self):
        if self.service_language:
            return self.service_language.pk
        return "fi"

    def get_registration_message(self, subject, cleaned_body, plain_text_body):
        [_, linked_registrations_ui_locale] = get_ui_locales(self.service_language)

        with override(linked_registrations_ui_locale):
            email_variables = get_signup_notification_variables(self)
            email_variables["body"] = cleaned_body

            rendered_body = render_to_string("message_to_signup.html", email_variables)

        return (
            subject,
            plain_text_body,
            rendered_body,
            settings.SUPPORT_EMAIL,
            [self.email],
        )

    def get_notification_message(
        self,
        notification_type,
        access_code=None,
        is_sub_event_cancellation=False,
        payment_link=None,
    ):
        [_, linked_registrations_ui_locale] = get_ui_locales(self.service_language)

        if notification_type == SignUpNotificationType.EVENT_CANCELLATION:
            email_template = "event_cancellation_confirmation.html"
        elif notification_type in (
            SignUpNotificationType.CANCELLATION,
            SignUpNotificationType.PAYMENT_EXPIRED,
        ):
            email_template = "cancellation_confirmation.html"
        elif notification_type in (
            SignUpNotificationType.CONFIRMATION,
            SignUpNotificationType.CONFIRMATION_WITH_PAYMENT,
            SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST,
            SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT,
            SignUpNotificationType.TRANSFER_AS_PARTICIPANT_WITH_PAYMENT,
        ):
            email_template = "common_signup_confirmation.html"
        else:
            raise ValueError(f"Invalid signup notification type: {notification_type}")

        with override(linked_registrations_ui_locale, deactivate=True):
            email_variables = get_signup_notification_variables(
                self, access_code=access_code
            )
            email_variables["texts"] = get_signup_notification_texts(
                self,
                notification_type,
                is_sub_event_cancellation=is_sub_event_cancellation,
            )
            email_variables["payment_url"] = payment_link

            rendered_body = render_to_string(
                email_template,
                email_variables,
            )

        return (
            get_signup_notification_subject(
                self,
                notification_type,
                is_sub_event_cancellation=is_sub_event_cancellation,
            ),
            rendered_body,
            get_email_noreply_address(),
            [self.email],
        )

    def send_notification(
        self,
        notification_type,
        access_code=None,
        is_sub_event_cancellation=False,
        payment_link=None,
    ):
        message = self.get_notification_message(
            notification_type,
            access_code=access_code,
            is_sub_event_cancellation=is_sub_event_cancellation,
            payment_link=payment_link,
        )
        rendered_body = message[1]

        email = EmailMultiAlternatives(*message)
        email.attach_alternative(rendered_body, "text/html")  # Optional HTML message

        if notification_type in [
            SignUpNotificationType.CONFIRMATION,
            SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST,
        ]:
            try:
                ics_attachment = create_event_ics_file_content(
                    self.registration.event, self.get_service_language_pk()
                )
                email.attach(*ics_attachment, "text/calendar")
            except ValueError as error:
                logger.error(error)

        email.send(fail_silently=False)

    def anonymize(self):
        self.email = anonymize_replacement
        self.phone_number = anonymize_replacement
        self.first_name = anonymize_replacement
        self.last_name = anonymize_replacement
        self.membership_number = anonymize_replacement
        self.save()

    def to_web_store_order_json(self):
        return {
            "firstName": self.first_name,
            "lastName": self.last_name,
            "email": self.email,
            "phone": self.phone_number,
        }


class SeatReservationCode(models.Model):
    seats = models.PositiveSmallIntegerField(
        verbose_name=_("Number of seats"), blank=False, default=0
    )
    registration = models.ForeignKey(
        Registration, on_delete=models.CASCADE, null=False, related_name="reservations"
    )
    code = models.UUIDField(
        verbose_name=_("Seat reservation code"), default=uuid4, editable=False
    )
    timestamp = models.DateTimeField(
        verbose_name=_("Timestamp"), auto_now_add=True, blank=True
    )

    @property
    def expiration(self):
        return self.timestamp + timedelta(minutes=code_validity_duration(self.seats))

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["registration", "code"], name="unique_seat_reservation"
            ),
        ]


class SignUpPriceGroup(RegistrationPriceGroupBaseModel, SoftDeletableBaseModel):
    """When a registration price group is selected when creating a signup for a registration,
    the pricing information that existed at that moment is stored into this model/table.
    """

    signup = models.OneToOneField(
        SignUp,
        related_name="price_group",
        on_delete=models.CASCADE,
    )

    registration_price_group = models.ForeignKey(
        RegistrationPriceGroup,
        related_name="signup_price_groups",
        on_delete=models.RESTRICT,
    )

    description = models.CharField(max_length=255)

    def to_web_store_order_json(self):
        # TODO: use a non-hardcoded productId once product mapping is implemented.
        return {
            "productId": "0d2be9c8-ad1e-3268-8d76-c94dbc3f6bcb",
            "productName": str(self.description),
            "quantity": 1,
            "unit": str(_("pcs")),
            "rowPriceNet": str(
                strip_trailing_zeroes_from_decimal(self.price_without_vat)
            ),
            "rowPriceVat": str(strip_trailing_zeroes_from_decimal(self.vat)),
            "rowPriceTotal": str(strip_trailing_zeroes_from_decimal(self.price)),
            "priceNet": str(strip_trailing_zeroes_from_decimal(self.price_without_vat)),
            "priceGross": str(strip_trailing_zeroes_from_decimal(self.price)),
            "priceVat": str(strip_trailing_zeroes_from_decimal(self.vat)),
            "vatPercentage": str(int(self.vat_percentage)),
        }


class SignUpPayment(
    SignUpOrGroupDependingMixin, CreatedModifiedBaseModel, SoftDeletableBaseModel
):
    class PaymentStatus:
        CREATED = "created"
        PAID = "paid"
        CANCELLED = "cancelled"
        REFUNDED = "refunded"
        EXPIRED = "expired"

    PAYMENT_STATUSES = (
        (PaymentStatus.CREATED, _("Created")),
        (PaymentStatus.PAID, _("Paid")),
        (PaymentStatus.CANCELLED, _("Cancelled")),
        (PaymentStatus.REFUNDED, _("Refunded")),
        (PaymentStatus.EXPIRED, _("Expired")),
    )

    # For signups that belong to a group.
    signup_group = models.OneToOneField(
        SignUpGroup,
        on_delete=models.CASCADE,
        related_name="payment",
        null=True,
        default=None,
    )

    # For signups that do not belong to a group.
    signup = models.OneToOneField(
        SignUp,
        on_delete=models.CASCADE,
        related_name="payment",
        null=True,
        default=None,
    )

    amount = models.DecimalField(max_digits=19, decimal_places=2)

    status = models.CharField(
        verbose_name=_("Payment status"),
        max_length=25,
        choices=PAYMENT_STATUSES,
        default=PaymentStatus.CREATED,
    )

    external_order_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        default=None,
    )

    expires_at = models.DateTimeField(
        verbose_name=_("Expires at"),
        null=True,
        blank=True,
        default=None,
    )

    checkout_url = models.URLField(null=True, blank=True, default=None)

    logged_in_checkout_url = models.URLField(null=True, blank=True, default=None)
