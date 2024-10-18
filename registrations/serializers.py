from datetime import timedelta
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils.timezone import localdate, localtime
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.fields import DateTimeField

from events.auth import ApiKeyUser
from events.fields import EventJSONLDRelatedField
from events.models import Event, Language
from events.utils import clean_text_fields
from helevents.models import User
from linkedevents.serializers import LinkedEventsSerializer, TranslatedModelSerializer
from linkedevents.utils import (
    get_fixed_lang_codes,
    validate_serializer_field_for_duplicates,
)
from registrations.exceptions import (
    ConflictException,
    WebStoreAPIError,
    WebStoreProductMappingValidationError,
)
from registrations.models import (
    VAT_CODE_MAPPING,
    VAT_PERCENTAGES,
    OfferPriceGroup,
    PriceGroup,
    Registration,
    RegistrationPriceGroup,
    RegistrationUserAccess,
    RegistrationWebStoreAccount,
    RegistrationWebStoreMerchant,
    RegistrationWebStoreProductMapping,
    SeatReservationCode,
    SignUp,
    SignUpContactPerson,
    SignUpGroup,
    SignUpGroupProtectedData,
    SignUpNotificationType,
    SignUpPayment,
    SignUpPaymentCancellation,
    SignUpPaymentRefund,
    SignUpPriceGroup,
    SignUpProtectedData,
    WebStoreAccount,
    WebStoreMerchant,
)
from registrations.permissions import CanAccessRegistrationSignups
from registrations.utils import (
    code_validity_duration,
    get_signup_create_url,
    has_allowed_substitute_user_email_domain,
)
from web_store.order.enums import (
    WebStoreOrderWebhookEventType,
    WebStoreRefundWebhookEventType,
)
from web_store.payment.enums import WebStorePaymentWebhookEventType


def _get_attending_and_waitlisted_capacities(
    registration: Registration, signups_count: int
) -> tuple[int, int]:
    attendee_capacity = registration.maximum_attendee_capacity
    waiting_list_capacity = registration.waiting_list_capacity
    add_as_attending = add_as_waitlisted = signups_count

    if attendee_capacity is not None:
        already_attending = SignUp.objects.filter(
            registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
        ).count()
        add_as_attending = attendee_capacity - already_attending

    if waiting_list_capacity is not None:
        already_waitlisted = SignUp.objects.filter(
            registration=registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        ).count()
        add_as_waitlisted = waiting_list_capacity - already_waitlisted

    return max(add_as_attending, 0), max(add_as_waitlisted, 0)


def _get_protected_data(validated_data: dict, keys: list[str]) -> dict:
    return {key: validated_data.pop(key) for key in keys if key in validated_data}


def _notify_contact_person(
    contact_person, attendee_status, current_user=None, payment_link=None
):
    if not contact_person:
        return

    confirmation_type_mapping = {
        SignUp.AttendeeStatus.ATTENDING: (
            SignUpNotificationType.CONFIRMATION_WITH_PAYMENT
            if payment_link
            else SignUpNotificationType.CONFIRMATION
        ),
        SignUp.AttendeeStatus.WAITING_LIST: SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST,
    }

    access_code = (
        contact_person.create_access_code()
        if contact_person.can_create_access_code(current_user) and not payment_link
        else None
    )

    contact_person.send_notification(
        confirmation_type_mapping[attendee_status],
        access_code=access_code,
        payment_link=payment_link,
    )


def _validate_registration_enrolment_times(
    registration: Registration, user: User
) -> None:
    enrolment_start_time = registration.enrolment_start_time
    enrolment_end_time = registration.enrolment_end_time
    current_time = localtime()

    if enrolment_start_time and current_time < enrolment_start_time:
        raise ConflictException(_("Enrolment is not yet open."))

    # Allow a superuser, registration admin, created_by event admin or a substitute user
    # to add signups to a closed registration.
    if (
        enrolment_end_time
        and current_time > enrolment_end_time
        and not (
            user.is_authenticated
            and (
                user.is_superuser
                or user.is_registration_admin_of(registration.publisher)
                or (
                    user.id == registration.created_by_id
                    and user.is_admin_of(registration.publisher)
                )
                or user.is_substitute_user_of(registration.registration_user_accesses)
            )
        )
    ):
        raise ConflictException(_("Enrolment is already closed."))


def _validate_contact_person_for_payment(contact_person: dict, errors: dict) -> None:
    if not contact_person or not (
        contact_person.get("first_name") and contact_person.get("last_name")
    ):
        errors["contact_person"] = _(
            "Contact person's first and last name are required to make a payment."
        )


def _validate_signups_for_payment(
    signups: list[dict], errors: dict, field_name: str
) -> None:
    if any(
        [
            signup
            for signup in signups
            if signup.get("price_group")
            and signup["price_group"]["registration_price_group"].price <= 0
        ]
    ):
        errors[field_name] = _(
            "Participants must have a price group with price greater than 0 "
            "selected to make a payment."
        )


class CreatedModifiedBaseSerializer(serializers.ModelSerializer):
    created_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"),
        required=False,
        allow_null=True,
        read_only=True,
    )

    last_modified_time = DateTimeField(
        default_timezone=ZoneInfo("UTC"),
        required=False,
        allow_null=True,
        read_only=True,
    )

    created_by = serializers.StringRelatedField(required=False, allow_null=True)
    last_modified_by = serializers.StringRelatedField(required=False, allow_null=True)

    is_created_by_current_user = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_created_by_current_user(self, obj):
        if not (request := self.context.get("request")):
            return False

        return request.user == obj.created_by

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        validated_data["last_modified_by"] = self.context["request"].user

        instance = super().create(validated_data)
        return instance

    def update(self, instance, validated_data):
        validated_data["last_modified_by"] = self.context["request"].user
        super().update(instance, validated_data)
        return instance

    class Meta:
        fields = (
            "created_time",
            "last_modified_time",
            "created_by",
            "last_modified_by",
        )


class SignUpContactPersonSerializer(serializers.ModelSerializer):
    service_language = serializers.PrimaryKeyRelatedField(
        queryset=Language.objects.filter(service_language=True),
        many=False,
        required=False,
    )

    def validate(self, data):
        # Clean html tags from the text fields
        data = clean_text_fields(data, strip=True)

        return super().validate(data)

    class Meta:
        fields = (
            "id",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "native_language",
            "service_language",
            "membership_number",
            "notifications",
        )
        model = SignUpContactPerson


class SignUpBaseSerializer(CreatedModifiedBaseSerializer):
    contact_person = SignUpContactPersonSerializer(required=False, allow_null=True)
    extra_info = serializers.CharField(required=False, allow_blank=True)
    has_contact_person_access = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_has_contact_person_access(self, obj):
        if not (request := self.context.get("request")):
            return False

        return request.user.is_authenticated and request.user.is_contact_person_of(obj)

    class Meta(CreatedModifiedBaseSerializer.Meta):
        fields = (
            "contact_person",
            "extra_info",
            "has_contact_person_access",
            "is_created_by_current_user",
        ) + CreatedModifiedBaseSerializer.Meta.fields


class SignUpPriceGroupSerializer(TranslatedModelSerializer):
    id = serializers.IntegerField(required=False, read_only=True)
    registration_price_group = serializers.PrimaryKeyRelatedField(
        queryset=RegistrationPriceGroup.objects.all()
    )
    price = serializers.DecimalField(
        required=False, read_only=True, max_digits=19, decimal_places=2
    )
    price_without_vat = serializers.DecimalField(
        required=False, read_only=True, max_digits=19, decimal_places=2
    )
    vat = serializers.DecimalField(
        required=False, read_only=True, max_digits=19, decimal_places=2
    )
    vat_percentage = serializers.DecimalField(
        required=False,
        read_only=True,
        max_digits=4,
        decimal_places=2,
    )

    def validate(self, data):
        validated_data = super().validate(data)

        if registration_price_group := validated_data.get("registration_price_group"):
            for lang_field in ("description_fi", "description_sv", "description_en"):
                validated_data[lang_field] = getattr(
                    registration_price_group.price_group, lang_field, None
                )

            for field in ("price", "price_without_vat", "vat", "vat_percentage"):
                validated_data[field] = getattr(registration_price_group, field)

        return validated_data

    class Meta:
        model = SignUpPriceGroup
        fields = [
            "id",
            "registration_price_group",
            "description",
            "price",
            "vat_percentage",
            "price_without_vat",
            "vat",
        ]
        extra_kwargs = {"description": {"required": False, "read_only": True}}


class SignUpPaymentSerializer(CreatedModifiedBaseSerializer):
    class Meta(CreatedModifiedBaseSerializer.Meta):
        fields = (
            "id",
            "signup_group",
            "signup",
            "external_order_id",
            "checkout_url",
            "logged_in_checkout_url",
            "amount",
            "status",
        ) + CreatedModifiedBaseSerializer.Meta.fields
        model = SignUpPayment
        extra_kwargs = {
            "signup_group": {"write_only": True},
            "signup": {"write_only": True},
        }


class WebStorePaymentBaseSerializer(serializers.Serializer):
    create_payment = serializers.BooleanField(required=False, write_only=True)
    payment = SignUpPaymentSerializer(required=False, read_only=True)

    @staticmethod
    def _create_payment(signup_or_group):
        try:
            return signup_or_group.create_web_store_payment()
        except (WebStoreAPIError, WebStoreProductMappingValidationError) as exc:
            raise serializers.ValidationError(exc.messages)

    class Meta:
        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields = ("create_payment", "payment")
        else:
            fields = ()


class SignUpPaymentRefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignUpPaymentRefund
        fields = (
            "id",
            "amount",
            "payment",
            "external_refund_id",
            "created_time",
        )


class SignUpPaymentCancellationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignUpPaymentCancellation
        fields = (
            "id",
            "payment",
            "created_time",
        )


class RefundOrCancellationRelationBaseSerializer(serializers.Serializer):
    payment_refund = SignUpPaymentRefundSerializer(read_only=True)
    payment_cancellation = SignUpPaymentCancellationSerializer(read_only=True)

    class Meta:
        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields = ("payment_refund", "payment_cancellation")
        else:
            fields = ()


class SignUpSerializer(
    SignUpBaseSerializer,
    WebStorePaymentBaseSerializer,
    RefundOrCancellationRelationBaseSerializer,
):
    view_name = "signup"
    id = serializers.IntegerField(required=False)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    def get_fields(self):
        fields = super().get_fields()

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields["price_group"] = SignUpPriceGroupSerializer(
                required=False,
                allow_null=True,
            )

        return fields

    @staticmethod
    def _update_or_create_protected_data(signup, **protected_data):
        if not protected_data:
            return

        SignUpProtectedData.objects.update_or_create(
            registration_id=signup.registration_id,
            signup=signup,
            defaults=protected_data,
        )

    @staticmethod
    def _update_or_create_contact_person(signup, **contact_person_data):
        if signup.signup_group_id or not contact_person_data:
            return None

        contact_person, _created = SignUpContactPerson.objects.update_or_create(
            signup=signup,
            defaults=contact_person_data,
        )

        return contact_person

    @staticmethod
    def _update_or_create_price_group(signup, **price_group_data):
        if not price_group_data or not settings.WEB_STORE_INTEGRATION_ENABLED:
            return

        SignUpPriceGroup.objects.update_or_create(
            signup=signup,
            defaults=price_group_data,
        )

    def create(self, validated_data):
        registration = validated_data["registration"]
        protected_data = _get_protected_data(
            validated_data, ["extra_info", "date_of_birth"]
        )
        contact_person_data = validated_data.pop("contact_person", None) or {}
        price_group_data = validated_data.pop("price_group", None) or {}
        create_payment = validated_data.pop("create_payment", False)

        add_as_attending, add_as_waitlisted = _get_attending_and_waitlisted_capacities(
            registration, 1
        )

        signup = None
        contact_person = None
        payment = None

        if not add_as_attending and add_as_waitlisted:
            validated_data["attendee_status"] = SignUp.AttendeeStatus.WAITING_LIST

        if add_as_attending or add_as_waitlisted:
            signup = super().create(validated_data)

            self._update_or_create_protected_data(signup, **protected_data)
            self._update_or_create_price_group(signup, **price_group_data)
            contact_person = self._update_or_create_contact_person(
                signup, **contact_person_data
            )

        if (
            create_payment
            and signup
            and signup.attendee_status == SignUp.AttendeeStatus.ATTENDING
            and not signup.signup_group_id
        ):
            # Payment can only be created here for an attending signup that is not part of a group.
            # A group will have a single shared payment that is created in the group serializer.
            payment = self._create_payment(signup)

        if signup:
            _notify_contact_person(
                contact_person,
                signup.attendee_status,
                current_user=self.context["request"].user,
                payment_link=getattr(payment, "checkout_url", None),
            )

            return signup

        raise DRFPermissionDenied(_("The waiting list is already full"))

    def update(self, instance, validated_data):
        errors = {}

        if (
            "attendee_status" in validated_data
            and instance.attendee_status != validated_data["attendee_status"]
        ):
            errors["attendee_status"] = _(
                "You may not change the attendee_status of an existing object."
            )
        if (
            "registration" in validated_data
            and instance.registration != validated_data["registration"]
        ):
            errors["registration"] = _(
                "You may not change the registration of an existing object."
            )

        if errors:
            raise serializers.ValidationError(errors)

        protected_data = _get_protected_data(
            validated_data, ["extra_info", "date_of_birth"]
        )
        contact_person_data = validated_data.pop("contact_person", None) or {}
        price_group_data = validated_data.pop("price_group", None) or {}

        super().update(instance, validated_data)
        self._update_or_create_protected_data(instance, **protected_data)
        self._update_or_create_price_group(instance, **price_group_data)

        contact_person = getattr(instance, "contact_person", None)
        if instance.signup_group_id and contact_person:
            # A signup in a group should never have a contact person - it's the group that has it,
            # so delete the individual signup's contact person.
            contact_person.delete()
        elif not instance.signup_group_id:
            self._update_or_create_contact_person(instance, **contact_person_data)

        return instance

    def _validate_mandatory_fields(self, registration, validated_data, errors):
        falsy_values = ("", None)

        for field in registration.mandatory_fields:
            if self.partial and field not in validated_data.keys():
                # Don't validate field if request method is PATCH and field is missing from the payload.
                continue
            elif validated_data.get(field) in falsy_values:
                errors[field] = _("This field must be specified.")

    def _validate_date_of_birth(self, registration, validated_data, errors):
        if (
            registration.audience_min_age is None
            and registration.audience_max_age is None
            or self.partial
            and "date_of_birth" not in validated_data.keys()
        ):
            # Don't validate date_of_birth if one of the following is true:
            # - audience_min_age and registration.audience_max_age are not defined
            # - request method is PATCH and field "date_of_birth" is missing from the payload
            return

        date_of_birth = validated_data.get("date_of_birth")

        if not date_of_birth:
            errors["date_of_birth"] = _("This field must be specified.")
        else:
            today = localdate()
            comparison_date = (
                max([today, registration.event.start_time.date()])
                if registration.event.start_time
                else today
            )

            age = (
                comparison_date.year
                - date_of_birth.year
                - (
                    (comparison_date.month, comparison_date.day)
                    < (date_of_birth.month, date_of_birth.day)
                )
            )

            if registration.audience_min_age and age < registration.audience_min_age:
                errors["date_of_birth"] = _("The participant is too young.")
            elif registration.audience_max_age and age > registration.audience_max_age:
                errors["date_of_birth"] = _("The participant is too old.")

    def _validate_price_group(self, registration, data, validated_data, errors):
        price_group = validated_data.get("price_group") or {}

        if (
            not price_group
            and registration.registration_price_groups.exists()
            and (not self.partial or "price_group" in data.keys())
        ):
            errors["price_group"] = _(
                "Price group selection is mandatory for this registration."
            )
        elif (
            (
                instance_id := validated_data.get(
                    "id", getattr(self.instance, "pk", None)
                )
            )
            and price_group.get("id")
            and registration.signups.exclude(pk=instance_id)
            .filter(price_group=price_group["id"])
            .exists()
        ):
            errors["price_group"] = _(
                "Price group is already assigned to another participant."
            )
        elif (
            registration_price_group := price_group.get("registration_price_group")
        ) and registration_price_group.registration_id != registration.pk:
            errors["price_group"] = _(
                "Price group is not one of the allowed price groups for this registration."
            )

    def validate(self, data):
        # Clean html tags from the text fields
        data = clean_text_fields(data, strip=True)

        validated_data = super().validate(data)

        errors = {}

        if isinstance(self.instance, SignUp):
            registration = self.instance.registration
        else:
            registration = validated_data["registration"]

        self._validate_mandatory_fields(registration, validated_data, errors)
        self._validate_date_of_birth(registration, validated_data, errors)

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            self._validate_price_group(registration, data, validated_data, errors)

            if validated_data.get("create_payment"):
                _validate_signups_for_payment([validated_data], errors, "price_group")

                _validate_contact_person_for_payment(
                    validated_data.get("contact_person"), errors
                )

        if errors:
            raise serializers.ValidationError(errors)

        return validated_data

    class Meta(
        SignUpBaseSerializer.Meta,
        WebStorePaymentBaseSerializer.Meta,
        RefundOrCancellationRelationBaseSerializer.Meta,
    ):
        fields = (
            "id",
            "anonymization_time",
            "first_name",
            "last_name",
            "date_of_birth",
            "phone_number",
            "city",
            "attendee_status",
            "street_address",
            "zipcode",
            "presence_status",
            "registration",
            "signup_group",
            "user_consent",
        ) + SignUpBaseSerializer.Meta.fields

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields += ("price_group",)
            fields += WebStorePaymentBaseSerializer.Meta.fields
            fields += RefundOrCancellationRelationBaseSerializer.Meta.fields

        model = SignUp


class WebStoreAccountBaseSerializer(serializers.ModelSerializer):
    class Meta:
        fields = (
            "name",
            "company_code",
            "main_ledger_account",
            "balance_profit_center",
            "internal_order",
            "profit_center",
            "project",
            "operation_area",
        )


class WebStoreAccountSerializer(
    WebStoreAccountBaseSerializer, CreatedModifiedBaseSerializer
):
    id = serializers.IntegerField(required=False)

    class Meta(WebStoreAccountBaseSerializer.Meta, CreatedModifiedBaseSerializer.Meta):
        model = WebStoreAccount
        fields = (
            "id",
            "active",
        )
        fields += WebStoreAccountBaseSerializer.Meta.fields
        fields += CreatedModifiedBaseSerializer.Meta.fields


class RegistrationWebStoreMerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationWebStoreMerchant
        fields = ("merchant",)


class RegistrationWebStoreAccountSerializer(WebStoreAccountBaseSerializer):
    def validate(self, data):
        validated_data = super().validate(data)

        if not self.partial or "account" in validated_data:
            validated_data["name"] = validated_data["account"].name

        return data

    class Meta(WebStoreAccountBaseSerializer.Meta):
        model = RegistrationWebStoreAccount
        fields = ("account",)
        fields += WebStoreAccountBaseSerializer.Meta.fields
        extra_kwargs = {
            "name": {"read_only": True},
        }


class GroupSignUpSerializer(SignUpSerializer):
    class Meta(SignUpSerializer.Meta):
        fields = [
            field
            for field in SignUpSerializer.Meta.fields
            if field not in ("contact_person", "create_payment")
        ]
        extra_kwargs = {
            "registration": {"required": False},
            "signup_group": {"read_only": True},
        }


class GroupSignUpCreateSerializer(GroupSignUpSerializer):
    class Meta(GroupSignUpSerializer.Meta):
        fields = [
            field for field in GroupSignUpSerializer.Meta.fields if field != "payment"
        ]


class RegistrationUserAccessIdField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        registration_id = self.context["request"].parser_context["kwargs"].get("pk")
        if not registration_id:
            return RegistrationUserAccess.objects.none()

        return RegistrationUserAccess.objects.filter(registration__pk=registration_id)


class RegistrationUserAccessCreateSerializer(serializers.ModelSerializer):
    language = serializers.PrimaryKeyRelatedField(
        queryset=Language.objects.filter(service_language=True),
        required=False,
        allow_null=True,
    )

    def validate(self, data):
        validated_data = super().validate(data)

        errors = {}

        email = validated_data["email"]
        if validated_data.get(
            "is_substitute_user"
        ) and not has_allowed_substitute_user_email_domain(email):
            errors["is_substitute_user"] = _(
                "The user's email domain is not one of the allowed domains for substitute users."
            )

        if errors:
            raise serializers.ValidationError(errors)

        return validated_data

    class Meta:
        model = RegistrationUserAccess
        fields = ["email", "language", "is_substitute_user"]


class RegistrationUserAccessSerializer(RegistrationUserAccessCreateSerializer):
    id = RegistrationUserAccessIdField(required=False, allow_null=True)

    class Meta(RegistrationUserAccessCreateSerializer.Meta):
        fields = ["id"] + RegistrationUserAccessCreateSerializer.Meta.fields


class PriceGroupRelatedField(serializers.PrimaryKeyRelatedField):
    def to_representation(self, value):
        price_group = PriceGroup.objects.only(
            "pk", "description_fi", "description_sv", "description_en"
        ).get(pk=value.pk)

        return {
            "id": price_group.pk,
            "description": {
                lang: getattr(price_group, f"description_{lang}")
                for lang in ("fi", "sv", "en")
                if getattr(price_group, f"description_{lang}", None) is not None
            },
        }


class RegistrationPriceGroupBaseSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    price_group = PriceGroupRelatedField(queryset=PriceGroup.objects.all())
    price = serializers.DecimalField(
        required=False, max_digits=19, decimal_places=2, min_value=Decimal("0.00")
    )
    price_without_vat = serializers.DecimalField(
        required=False, read_only=True, max_digits=19, decimal_places=2
    )
    vat = serializers.DecimalField(
        required=False, read_only=True, max_digits=19, decimal_places=2
    )
    vat_percentage = serializers.DecimalField(
        required=False,
        max_digits=4,
        decimal_places=2,
        min_value=Decimal("0.00"),
        max_value=Decimal("99.99"),
    )

    def validate(self, data):
        validated_data = super().validate(data)

        errors = {}

        vat_percentage = validated_data.get("vat_percentage")
        if vat_percentage not in [vat[0] for vat in VAT_PERCENTAGES]:
            errors["vat_percentage"] = _("%(value)s is not a valid choice.") % {
                "value": vat_percentage
            }

        if validated_data["price_group"].is_free:
            validated_data["price"] = Decimal("0")
        elif validated_data.get("price") is None:
            errors["price"] = _("Price must be greater than or equal to 0.")

        if errors:
            raise serializers.ValidationError(errors)

        return validated_data

    class Meta:
        fields = [
            "id",
            "price_group",
            "price",
            "vat_percentage",
            "price_without_vat",
            "vat",
        ]


class OfferPriceGroupSerializer(RegistrationPriceGroupBaseSerializer):
    class Meta(RegistrationPriceGroupBaseSerializer.Meta):
        model = OfferPriceGroup


class RegistrationPriceGroupSerializer(RegistrationPriceGroupBaseSerializer):
    class Meta(RegistrationPriceGroupBaseSerializer.Meta):
        model = RegistrationPriceGroup


class RegistrationSerializer(LinkedEventsSerializer, CreatedModifiedBaseSerializer):
    view_name = "registration-detail"

    only_admin_visible_fields = (
        "created_by",
        "last_modified_by",
        "registration_user_accesses",
    )

    event = EventJSONLDRelatedField(
        serializer="events.serializers.EventSerializer",
        many=False,
        view_name="event-detail",
        queryset=Event.objects.all(),
    )

    signups = serializers.SerializerMethodField()

    current_attendee_count = serializers.SerializerMethodField()

    current_waiting_list_count = serializers.SerializerMethodField()

    remaining_attendee_capacity = serializers.SerializerMethodField()

    remaining_waiting_list_capacity = serializers.SerializerMethodField()

    data_source = serializers.SerializerMethodField()

    publisher = serializers.SerializerMethodField()

    has_registration_user_access = serializers.SerializerMethodField()

    has_substitute_user_access = serializers.SerializerMethodField()

    signup_url = serializers.SerializerMethodField()

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        context = self.context
        instance = self.instance

        if instance:
            self.fields["event"].read_only = True

        self.registration_admin_tree_ids = context.get(
            "registration_admin_tree_ids", set()
        )

    def get_fields(self):
        fields = super().get_fields()

        if self.instance is None:
            fields["registration_user_accesses"] = (
                RegistrationUserAccessCreateSerializer(many=True, required=False)
            )
        else:
            fields["registration_user_accesses"] = RegistrationUserAccessSerializer(
                many=True, required=False
            )

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields["registration_price_groups"] = RegistrationPriceGroupSerializer(
                many=True,
                required=False,
            )
            fields["registration_merchant"] = RegistrationWebStoreMerchantSerializer(
                required=False,
            )
            fields["registration_account"] = RegistrationWebStoreAccountSerializer(
                required=False,
                partial=self.partial,
            )

        return fields

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_has_registration_user_access(self, obj):
        user = self.user

        has_registration_user_access = (
            user.is_authenticated
            and user.is_strongly_identified
            and obj.registration_user_accesses.filter(email=user.email).exists()
        )

        return has_registration_user_access or self.get_has_substitute_user_access(obj)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_has_substitute_user_access(self, obj):
        user = self.user
        return user.is_authenticated and user.is_substitute_user_of(
            obj.registration_user_accesses
        )

    @extend_schema_field(SignUpSerializer(many=True, read_only=True))
    def get_signups(self, obj):
        params = self.context["request"].query_params

        if "signups" in params.get("include", "").split(","):
            # Only organization registration admins or the registration user
            # should be able to access the signup information.
            permission = CanAccessRegistrationSignups()
            if permission.has_permission(
                self.context["request"], self.context["view"]
            ) and permission.has_object_permission(
                self.context["request"], self.context["view"], obj
            ):
                signups = obj.signups.all()
                return SignUpSerializer(signups, many=True, read_only=True).data

        return None

    @extend_schema_field(OpenApiTypes.INT)
    def get_current_attendee_count(self, obj):
        return obj.current_attendee_count

    @extend_schema_field(OpenApiTypes.INT)
    def get_current_waiting_list_count(self, obj):
        return obj.current_waiting_list_count

    @extend_schema_field(Optional[int])
    def get_remaining_attendee_capacity(self, obj):
        # Because there can be slight delay with capacity calculations in case of seat expiration,
        # calculate the current value on the fly so that front-end gets the most recent information.
        return obj.calculate_remaining_attendee_capacity()

    @extend_schema_field(Optional[int])
    def get_remaining_waiting_list_capacity(self, obj):
        # Because there can be slight delay with capacity calculations in case of seat expiration,
        # calculate the current value on the fly so that front-end gets the most recent information.
        return obj.calculate_remaining_waiting_list_capacity()

    @extend_schema_field(OpenApiTypes.STR)
    def get_data_source(self, obj):
        return obj.data_source.id

    @extend_schema_field(OpenApiTypes.STR)
    def get_publisher(self, obj):
        return obj.publisher.id

    @extend_schema_field(
        {
            "type": "object",
            "properties": {
                "en": {"type": "string"},
                "fi": {"type": "string"},
                "sv": {"type": "string"},
            },
        }
    )
    def get_signup_url(self, obj):
        return {lang: get_signup_create_url(obj, lang) for lang in ["en", "fi", "sv"]}

    # Override this method to allow only_admin_visible_fields also to
    # registration admin users
    def are_only_admin_visible_fields_allowed(self, obj):
        user = self.user

        return not user.is_anonymous and (
            obj.publisher.tree_id in self.admin_tree_ids
            or obj.publisher.tree_id in self.registration_admin_tree_ids
            or user.is_substitute_user_of(obj.registration_user_accesses)
        )

    @staticmethod
    def _create_or_update_registration_user_accesses(
        registration, registration_user_accesses
    ):
        for data in registration_user_accesses:
            if current_obj := data.pop("id", None):
                current_id = current_obj.id
            else:
                current_id = None

            try:
                RegistrationUserAccess.objects.update_or_create(
                    id=current_id,
                    registration=registration,
                    defaults=data,
                )

            except IntegrityError as error:
                if "duplicate key value violates unique constraint" in str(error):
                    raise serializers.ValidationError(
                        {
                            "registration_user_accesses": [
                                ErrorDetail(
                                    _(
                                        "Registration user access with email %(email)s already exists."
                                    )
                                    % {"email": data["email"]},
                                    code="unique",
                                )
                            ]
                        }
                    )
                else:
                    raise

    @staticmethod
    def _create_or_update_registration_price_groups(
        registration, registration_price_groups
    ):
        price_groups = []

        for data in registration_price_groups:
            price_groups.append(
                RegistrationPriceGroup.objects.update_or_create(
                    id=data.pop("id", None),
                    registration=registration,
                    defaults=data,
                )[0]
            )

        return price_groups

    @staticmethod
    def _create_or_update_registration_merchant(registration, registration_merchant):
        if not registration_merchant:
            return None, False

        registration_merchant["external_merchant_id"] = registration_merchant[
            "merchant"
        ].merchant_id

        instance = getattr(registration, "registration_merchant", None)
        has_changed = instance is None or instance.data_has_changed(
            registration_merchant
        )

        if instance:
            for field in registration_merchant:
                setattr(instance, field, registration_merchant[field])
            instance.save(update_fields=registration_merchant.keys())
        else:
            instance = RegistrationWebStoreMerchant.objects.create(
                registration=registration,
                **registration_merchant,
            )

        return instance, has_changed

    @staticmethod
    def _create_or_update_registration_account(registration, registration_account):
        if not registration_account:
            return None, False

        instance = getattr(registration, "registration_account", None)
        has_changed = instance is None or instance.data_has_changed(
            registration_account
        )

        if instance:
            for field in registration_account:
                setattr(instance, field, registration_account[field])
            instance.save(update_fields=registration_account.keys())
        else:
            instance = RegistrationWebStoreAccount.objects.create(
                registration=registration,
                **registration_account,
            )

        return instance, has_changed

    @transaction.atomic
    def create(self, validated_data):
        user = self.request.user
        if isinstance(user, ApiKeyUser):
            # allow creating a registration only if the api key matches event data source
            if (
                "event" in validated_data
                and validated_data["event"].data_source != user.data_source
            ):
                raise PermissionDenied(
                    _("Object data source does not match user data source")
                )

        registration_user_accesses = validated_data.pop(
            "registration_user_accesses", []
        )
        registration_price_groups = validated_data.pop("registration_price_groups", [])
        registration_merchant = validated_data.pop("registration_merchant", None)
        registration_account = validated_data.pop("registration_account", None)

        try:
            registration = super().create(validated_data)
        except IntegrityError as error:
            if "duplicate key value violates unique constraint" in str(error):
                raise serializers.ValidationError(
                    {"event": _("Event already has a registration.")}
                )
            else:
                raise

        # Create registration user accesses and send invitation email to them
        self._create_or_update_registration_user_accesses(
            registration, registration_user_accesses
        )

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            price_groups = self._create_or_update_registration_price_groups(
                registration, registration_price_groups
            )

            merchant, __ = self._create_or_update_registration_merchant(
                registration, registration_merchant
            )

            account, __ = self._create_or_update_registration_account(
                registration, registration_account
            )

            if price_groups and merchant and account:
                registration.create_or_update_web_store_product_mapping_and_accounting()

        return registration

    @transaction.atomic
    def update(self, instance, validated_data):
        registration_user_accesses = validated_data.pop(
            "registration_user_accesses", None
        )
        registration_price_groups = validated_data.pop(
            "registration_price_groups", None
        )
        registration_merchant = validated_data.pop("registration_merchant", None)
        registration_account = validated_data.pop("registration_account", None)

        # update validated fields
        super().update(instance, validated_data)

        def update_related(related_data: list, related_name: str):
            ids = [
                getattr(
                    data["id"], "id", data["id"]
                )  # user access has an object in the "id" field
                for data in related_data
                if data.get("id") is not None
            ]

            # Delete related objects which are not included in the payload
            getattr(instance, related_name).exclude(pk__in=ids).delete()

            # Update or create related objects
            return getattr(self, f"_create_or_update_{related_name}")(
                instance, related_data
            )

        # update registration users
        if isinstance(registration_user_accesses, list):
            update_related(registration_user_accesses, "registration_user_accesses")

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            if isinstance(registration_price_groups, list):
                price_groups = update_related(
                    registration_price_groups, "registration_price_groups"
                )
            else:
                price_groups = None

            __, merchant_has_changed = self._create_or_update_registration_merchant(
                instance, registration_merchant
            )

            __, account_has_changed = self._create_or_update_registration_account(
                instance, registration_account
            )

            if (
                merchant_has_changed
                or account_has_changed
                or (
                    price_groups
                    and not RegistrationWebStoreProductMapping.objects.filter(
                        registration=instance,
                        vat_code=VAT_CODE_MAPPING[price_groups[0].vat_percentage],
                    ).exists()
                )
            ):
                instance.create_or_update_web_store_product_mapping_and_accounting()

        return instance

    def validate_registration_user_accesses(self, value):
        def error_detail_callback(email):
            return ErrorDetail(
                _("Registration user access with email %(email)s already exists.")
                % {"email": email},
                code="unique",
            )

        return validate_serializer_field_for_duplicates(
            value, "email", error_detail_callback
        )

    def validate_registration_price_groups(self, value):
        def duplicate_error_detail_callback(price_group):
            return ErrorDetail(
                _(
                    "Registration price group with price_group %(price_group)s already exists."
                )
                % {"price_group": price_group},
                code="unique",
            )

        validate_serializer_field_for_duplicates(
            value, "price_group", duplicate_error_detail_callback
        )

        if value and not all(
            [
                price_group["vat_percentage"] == value[0]["vat_percentage"]
                for price_group in value
            ]
        ):
            raise serializers.ValidationError(
                {
                    "price_group": [
                        ErrorDetail(
                            _(
                                "All registration price groups must have the same VAT percentage."
                            ),
                            code="vat_percentage",
                        )
                    ]
                }
            )

        return value

    def _validate_merchant_and_account(self, data, errors):
        if not (
            data.get("registration_price_groups")
            or self.instance is not None
            and self.instance.registration_price_groups.exists()
        ):
            # Price groups not given or they don't exist => no need to validate.
            return

        if not data.get("registration_merchant") and (
            not self.partial or "registration_merchant" in data.keys()
        ):
            errors["registration_merchant"] = _(
                "This field is required when registration has customer groups."
            )

        if not data.get("registration_account") and (
            not self.partial or "registration_account" in data.keys()
        ):
            errors["registration_account"] = _(
                "This field is required when registration has customer groups."
            )

    def _validate_registration_price_groups(self, data, errors):
        if not (
            data.get("registration_merchant")
            or data.get("registration_account")
            or self.instance is not None
            and (
                getattr(self.instance, "registration_merchant", None) is not None
                or getattr(self.instance, "registration_account", None) is not None
            )
        ):
            # Merchant and account not given or they don't exist => no need to validate.
            return

        if not data.get("registration_price_groups") and (
            not self.partial or "registration_price_groups" in data.keys()
        ):
            errors["registration_price_groups"] = _(
                "This field is required when registration has a merchant or account."
            )

    # LinkedEventsSerializer validates name which doesn't exist in Registration model
    def validate(self, data):
        # Clean html tags from the text fields
        data = clean_text_fields(
            data, ["confirmation_message", "instructions"], strip=True
        )

        errors = {}

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            self._validate_merchant_and_account(data, errors)
            self._validate_registration_price_groups(data, errors)

        if errors:
            raise serializers.ValidationError(errors)

        return data

    class Meta(CreatedModifiedBaseSerializer.Meta):
        model = Registration

        fields = (
            "id",
            "signups",
            "current_attendee_count",
            "current_waiting_list_count",
            "remaining_attendee_capacity",
            "remaining_waiting_list_capacity",
            "data_source",
            "publisher",
            "registration_user_accesses",
            "has_registration_user_access",
            "has_substitute_user_access",
            "event",
            "attendee_registration",
            "audience_min_age",
            "audience_max_age",
            "enrolment_start_time",
            "enrolment_end_time",
            "maximum_attendee_capacity",
            "minimum_attendee_capacity",
            "waiting_list_capacity",
            "maximum_group_size",
            "mandatory_fields",
            "confirmation_message",
            "instructions",
            "signup_url",
            "is_created_by_current_user",
        ) + CreatedModifiedBaseSerializer.Meta.fields

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields += (
                "registration_price_groups",
                "registration_merchant",
                "registration_account",
            )

        extra_kwargs = {
            "maximum_attendee_capacity": {"required": True, "allow_null": False},
        }


class CreateSignUpsSerializer(serializers.Serializer):
    reservation_code = serializers.CharField()
    registration = serializers.PrimaryKeyRelatedField(
        queryset=Registration.objects.all(),
        many=False,
        required=True,
    )
    signups = SignUpSerializer(many=True, required=True)

    def validate(self, data):
        reservation_code = data["reservation_code"]
        registration = data["registration"]
        # Clean html tags from the text fields
        data = clean_text_fields(data, strip=True)
        user = self.context["request"].user

        # Prevent to signup if enrolment is not open.
        # Raises 409 error if enrolment is not open
        _validate_registration_enrolment_times(registration, user)

        try:
            reservation = SeatReservationCode.objects.get(
                code=reservation_code, registration=registration
            )
            data["reservation"] = reservation
        except SeatReservationCode.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "reservation_code": ErrorDetail(
                        _("Reservation code doesn't exist."),
                        code="does_not_exist",
                    )
                }
            )

        expiration = reservation.timestamp + timedelta(
            minutes=code_validity_duration(reservation.seats)
        )
        if localtime() > expiration:
            raise serializers.ValidationError(
                {"reservation_code": "Reservation code has expired."}
            )

        maximum_group_size = registration.maximum_group_size

        # Validate maximum group size
        if maximum_group_size is not None and len(data["signups"]) > maximum_group_size:
            raise serializers.ValidationError(
                {
                    "signups": ErrorDetail(
                        _(
                            "Amount of signups is greater than maximum group size: {max_group_size}."
                        ).format(max_group_size=maximum_group_size),
                        code="max_group_size",
                    )
                }
            )

        signups_count = len(data["signups"])

        if signups_count > reservation.seats:
            raise serializers.ValidationError(
                {"signups": "Number of signups exceeds the number of requested seats"}
            )

        if (
            settings.WEB_STORE_INTEGRATION_ENABLED
            and signups_count > 1
            and any([signup.get("create_payment") for signup in data["signups"]])
        ):
            raise serializers.ValidationError(
                {
                    "signups": _(
                        "Only one signup is supported when creating a Talpa web store payment."
                    )
                }
            )

        data = super().validate(data)
        return data

    def notify_contact_persons(self, signup_instances):
        user = self.context["request"].user

        for signup in signup_instances:
            if signup.signup_group_id:
                continue

            contact_person = getattr(signup, "contact_person", None)
            _notify_contact_person(
                contact_person, signup.attendee_status, current_user=user
            )

    def create_signups(self, validated_data):
        user = self.context["request"].user
        registration = validated_data["registration"]

        add_as_attending, add_as_waitlisted = _get_attending_and_waitlisted_capacities(
            registration, len(validated_data["signups"])
        )
        if not (add_as_attending or add_as_waitlisted):
            raise DRFPermissionDenied(_("The waiting list is already full"))

        capacity_by_attendee_status_map = {
            SignUp.AttendeeStatus.ATTENDING: add_as_attending,
            SignUp.AttendeeStatus.WAITING_LIST: add_as_waitlisted,
        }

        def check_and_set_attendee_status(cleaned_signup_data):
            if capacity_by_attendee_status_map.get(
                cleaned_signup_data.get("attendee_status")
            ):
                return

            if capacity_by_attendee_status_map[SignUp.AttendeeStatus.ATTENDING]:
                cleaned_signup_data["attendee_status"] = SignUp.AttendeeStatus.ATTENDING
            else:
                cleaned_signup_data["attendee_status"] = (
                    SignUp.AttendeeStatus.WAITING_LIST
                )

        signups = []

        for signup_data in validated_data["signups"]:
            if not (
                capacity_by_attendee_status_map[SignUp.AttendeeStatus.ATTENDING] > 0
                or capacity_by_attendee_status_map[SignUp.AttendeeStatus.WAITING_LIST]
                > 0
            ):
                break

            cleaned_signup_data = signup_data.copy()
            cleaned_signup_data["created_by"] = user
            cleaned_signup_data["last_modified_by"] = user

            check_and_set_attendee_status(cleaned_signup_data)
            capacity_by_attendee_status_map[cleaned_signup_data["attendee_status"]] -= 1

            extra_info = cleaned_signup_data.pop("extra_info", None)
            date_of_birth = cleaned_signup_data.pop("date_of_birth", None)
            contact_person = cleaned_signup_data.pop("contact_person", None)
            price_group = cleaned_signup_data.pop("price_group", None)
            cleaned_signup_data.pop("create_payment", False)

            signup = SignUp(**cleaned_signup_data)

            signup._extra_info = extra_info
            signup._date_of_birth = date_of_birth
            signup._contact_person = contact_person
            signup._price_group = price_group

            signups.append(signup)

        signup_instances = SignUp.objects.bulk_create(signups)

        SignUpProtectedData.objects.bulk_create(
            [
                SignUpProtectedData(
                    registration=registration,
                    signup=signup,
                    extra_info=signup._extra_info,
                    date_of_birth=signup._date_of_birth,
                )
                for signup in signups
                if signup._extra_info or signup._date_of_birth
            ]
        )

        SignUpContactPerson.objects.bulk_create(
            [
                SignUpContactPerson(signup=signup, **signup._contact_person)
                for signup in signups
                if signup._contact_person
            ]
        )

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            SignUpPriceGroup.objects.bulk_create(
                [
                    SignUpPriceGroup(signup=signup, **signup._price_group)
                    for signup in signups
                    if signup._price_group
                ]
            )

        return signup_instances


class SignUpGroupCreateSerializer(
    SignUpBaseSerializer,
    CreateSignUpsSerializer,
    WebStorePaymentBaseSerializer,
):
    reservation_code = serializers.CharField(write_only=True)
    contact_person = SignUpContactPersonSerializer(required=True)
    signups = GroupSignUpCreateSerializer(many=True, required=True)

    def validate(self, data):
        # Clean html tags from the text fields
        data = clean_text_fields(data, strip=True)
        validated_data = super().validate(data)

        errors = {}

        contact_person = validated_data.get("contact_person")
        if not contact_person:
            # The field can be given as an empty dict even if it's required
            # => need to validate this here.
            errors["contact_person"] = _(
                "Contact person information must be provided for a group."
            )

        if validated_data.get("create_payment"):
            _validate_signups_for_payment(validated_data["signups"], errors, "signups")

            _validate_contact_person_for_payment(
                contact_person,
                errors,
            )

        if errors:
            raise serializers.ValidationError(errors)

        return validated_data

    @staticmethod
    def _create_protected_data(signup_group, **protected_data):
        if not protected_data:
            return

        SignUpGroupProtectedData.objects.create(
            registration_id=signup_group.registration_id,
            signup_group=signup_group,
            **protected_data,
        )

    @staticmethod
    def _create_contact_person(signup_group, **contact_person_data):
        return SignUpContactPerson.objects.create(
            signup_group=signup_group,
            **contact_person_data,
        )

    def create(self, validated_data):
        validated_data.pop("reservation_code")
        reservation = validated_data.pop("reservation")
        signups_data = validated_data.pop("signups")
        protected_data = _get_protected_data(validated_data, ["extra_info"])
        contact_person_data = validated_data.pop("contact_person")
        create_payment = validated_data.pop("create_payment", False)

        instance = super().create(validated_data)
        self._create_protected_data(instance, **protected_data)

        for signup in signups_data:
            signup["signup_group"] = instance
        validated_data["signups"] = signups_data
        self.create_signups(validated_data)

        contact_person = self._create_contact_person(instance, **contact_person_data)
        payment = None

        if create_payment and instance.attending_signups:
            payment = self._create_payment(instance)

        if payment or instance.attending_signups:
            attendee_status = SignUp.AttendeeStatus.ATTENDING
        else:
            attendee_status = SignUp.AttendeeStatus.WAITING_LIST
        _notify_contact_person(
            contact_person,
            attendee_status,
            current_user=self.context["request"].user,
            payment_link=getattr(payment, "checkout_url", None),
        )

        reservation.delete()

        return instance

    class Meta(SignUpBaseSerializer.Meta, WebStorePaymentBaseSerializer.Meta):
        fields = (
            "id",
            "registration",
            "reservation_code",
            "signups",
            "anonymization_time",
        ) + SignUpBaseSerializer.Meta.fields

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields += WebStorePaymentBaseSerializer.Meta.fields

        model = SignUpGroup


class SignUpGroupSerializer(
    SignUpBaseSerializer, RefundOrCancellationRelationBaseSerializer
):
    view_name = "signupgroup-detail"

    @staticmethod
    def _update_protected_data(signup_group, **protected_data):
        if not protected_data:
            return

        SignUpGroupProtectedData.objects.update_or_create(
            registration_id=signup_group.registration_id,
            signup_group=signup_group,
            defaults=protected_data,
        )

    @staticmethod
    def _update_contact_person(signup_group, **contact_person_data):
        if not contact_person_data:
            return

        SignUpContactPerson.objects.update_or_create(
            signup_group=signup_group,
            defaults=contact_person_data,
        )

    def get_fields(self):
        fields = super().get_fields()

        fields["signups"] = GroupSignUpSerializer(
            many=True, required=False, partial=self.partial
        )

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields["payment"] = SignUpPaymentSerializer(read_only=True, required=False)

        return fields

    def validate(self, data):
        # Clean html tags from the text fields
        data = clean_text_fields(data, strip=True)

        validated_data = super().validate(data)

        errors = {}

        if (
            "registration" in validated_data
            and self.instance
            and self.instance.registration != validated_data["registration"]
        ):
            errors["registration"] = _(
                "You may not change the registration of an existing object."
            )

        if errors:
            raise serializers.ValidationError(errors)

        return validated_data

    def _update_signups(self, instance, validated_signups_data):
        for signup_data in validated_signups_data:
            if not signup_data.get("id"):
                continue

            if not self.partial:
                signup_data["signup_group"] = instance

            signup = SignUp.objects.get(pk=signup_data["id"])
            signup_serializer = SignUpSerializer(
                instance=signup,
                data=signup_data,
                context=self.context,
                partial=self.partial,
            )
            signup_serializer.update(signup_serializer.instance, signup_data)

    def update(self, instance, validated_data):
        signups_data = validated_data.pop("signups", [])
        protected_data = _get_protected_data(validated_data, ["extra_info"])
        contact_person_data = validated_data.pop("contact_person", None) or {}

        validated_data["last_modified_by"] = self.context["request"].user

        super().update(instance, validated_data)
        self._update_protected_data(instance, **protected_data)
        self._update_contact_person(instance, **contact_person_data)
        self._update_signups(instance, signups_data)

        return instance

    class Meta(
        SignUpBaseSerializer.Meta, RefundOrCancellationRelationBaseSerializer.Meta
    ):
        fields = (
            "id",
            "registration",
            "signups",
            "anonymization_time",
        ) + SignUpBaseSerializer.Meta.fields

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields += ("payment",)
            fields += RefundOrCancellationRelationBaseSerializer.Meta.fields

        model = SignUpGroup


class SeatReservationCodeSerializer(serializers.ModelSerializer):
    seats = serializers.IntegerField(required=True)

    timestamp = DateTimeField(
        default_timezone=ZoneInfo("UTC"), required=False, read_only=True
    )

    expiration = serializers.SerializerMethodField()

    in_waitlist = serializers.SerializerMethodField()

    def get_fields(self):
        fields = super().get_fields()

        if not self.instance:
            fields["code"] = serializers.UUIDField(required=False, read_only=True)
        else:
            fields["code"] = serializers.UUIDField(required=True)

        return fields

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_expiration(self, obj):
        return obj.expiration

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_in_waitlist(self, obj):
        registration = obj.registration
        maximum_attendee_capacity = registration.maximum_attendee_capacity

        if maximum_attendee_capacity is None:
            return False

        attendee_count = registration.signups.filter(
            attendee_status=SignUp.AttendeeStatus.ATTENDING
        ).count()

        return maximum_attendee_capacity - attendee_count <= 0

    def to_internal_value(self, data):
        if self.instance:
            data["registration"] = self.instance.registration.id
        return super().to_internal_value(data)

    def validate_code(self, value):
        if self.instance and value != self.instance.code:
            raise serializers.ValidationError(
                ErrorDetail(_("The value doesn't match."), code="mismatch")
            )

        return value

    def _validate_registration_group_size(self, registration, validated_data, errors):
        maximum_group_size = registration.maximum_group_size
        if maximum_group_size is None:
            return

        if validated_data["seats"] > maximum_group_size:
            errors["seats"] = ErrorDetail(
                _(
                    "Amount of seats is greater than maximum group size: {max_group_size}."
                ).format(max_group_size=maximum_group_size),
                code="max_group_size",
            )

    def _validate_registration_capacities(self, registration, validated_data, errors):
        maximum_attendee_capacity = registration.maximum_attendee_capacity
        if maximum_attendee_capacity is None:
            # Validate attendee capacity only if maximum_attendee_capacity is defined.
            return

        if self.instance:
            reserved_seats_amount = max(
                registration.reserved_seats_amount - self.instance.seats, 0
            )
        else:
            reserved_seats_amount = registration.reserved_seats_amount

        attendee_count = registration.current_attendee_count
        attendee_capacity_left = maximum_attendee_capacity - attendee_count

        # Only allow to reserve seats to event if there is attendee capacity is not used
        if attendee_capacity_left > 0:
            # Prevent to reserve seats if all available seats are already reserved
            if validated_data["seats"] > attendee_capacity_left - reserved_seats_amount:
                errors["seats"] = _(
                    "Not enough seats available. Capacity left: {capacity_left}."
                ).format(
                    capacity_left=max(attendee_capacity_left - reserved_seats_amount, 0)
                )
        elif (waiting_list_capacity := registration.waiting_list_capacity) is not None:
            # Validate waiting list capacity only if waiting_list_capacity is defined and
            # all seats in the event are used.
            waiting_list_count = registration.current_waiting_list_count
            waiting_list_capacity_left = waiting_list_capacity - waiting_list_count

            # Prevent to reserve seats to waiting list if all available seats in waiting list
            # are already reserved
            if (
                validated_data["seats"]
                > waiting_list_capacity_left - reserved_seats_amount
            ):
                errors["seats"] = _(
                    "Not enough capacity in the waiting list. Capacity left: {capacity_left}."
                ).format(
                    capacity_left=max(
                        waiting_list_capacity_left - reserved_seats_amount, 0
                    )
                )

    def validate(self, data):
        validated_data = super().validate(data)

        errors = {}

        registration = validated_data["registration"]
        user = self.context["request"].user

        # Prevent to reserve seats if enrolment is not open.
        # Raises 409 error if enrolment is not open
        _validate_registration_enrolment_times(registration, user)

        self._validate_registration_group_size(registration, validated_data, errors)
        self._validate_registration_capacities(registration, validated_data, errors)

        if errors:
            raise serializers.ValidationError(errors)

        return validated_data

    def update(self, instance, validated_data):
        if localtime() > instance.expiration:
            raise ConflictException(_("Cannot update expired seats reservation."))

        return super().update(instance, validated_data)

    class Meta:
        fields = (
            "id",
            "registration",
            "seats",
            "in_waitlist",
            "code",
            "timestamp",
            "expiration",
        )
        model = SeatReservationCode


class MassEmailSignupGroupsField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        registration = self.context["request"].data["registration"]

        return registration.signup_groups.filter(contact_person__email__isnull=False)


class MassEmailSignupsField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        registration = self.context["request"].data["registration"]

        return registration.signups.filter(contact_person__email__isnull=False)


class MassEmailSerializer(serializers.Serializer):
    subject = serializers.CharField()
    body = serializers.CharField()
    signup_groups = MassEmailSignupGroupsField(
        many=True,
        required=False,
    )
    signups = MassEmailSignupsField(
        many=True,
        required=False,
    )

    class Meta:
        model = Registration


class RegistrationSignupsExportSerializer(serializers.Serializer):
    ui_language = serializers.ChoiceField(
        choices=["en", "sv", "fi"],
        default="fi",
    )

    class Meta:
        model = Registration


class PriceGroupSerializer(TranslatedModelSerializer, CreatedModifiedBaseSerializer):
    def _any_required_description_translation_exists(self, data, validated_data):
        """
        Validates the translated description fields for Finnish, English and Swedish by checking
        that there is a description for at least one of the languages. This is due to the web store
        integration that supports the three languages.

        Description is considered valid if
        1. request is PATCH without any description fields given in data, OR
        2. any of the description fields have a valid value.
        """

        description_fields = ["description_fi", "description_en", "description_sv"]

        def any_description_field_in_data():
            return any([field in data.keys() for field in description_fields])

        def any_description_field_has_valid_value():
            return any([validated_data.get(field) for field in description_fields])

        return (
            self.partial and not any_description_field_in_data()
        ) or any_description_field_has_valid_value()

    def _description_exceeds_max_length(self, validated_data):
        for lang_code in get_fixed_lang_codes():
            field = f"description_{lang_code}"
            if (
                validated_data.get(field)
                and len(validated_data[field]) > PriceGroup.description.field.max_length
            ):
                return True

        return False

    def validate(self, data):
        # Clean html tags from the text fields
        data = clean_text_fields(data, strip=True)

        validated_data = super().validate(data)

        errors = {}

        if not self._any_required_description_translation_exists(data, validated_data):
            errors["description"] = _("This field is required.")
        elif self._description_exceeds_max_length(validated_data):
            errors["description"] = _(
                "Description can be at most %(max_length)s characters long."
            ) % {"max_length": PriceGroup.description.field.max_length}

        if errors:
            raise serializers.ValidationError(errors)

        return validated_data

    class Meta(CreatedModifiedBaseSerializer.Meta):
        fields = (
            "id",
            "publisher",
            "description",
            "is_free",
        ) + CreatedModifiedBaseSerializer.Meta.fields
        model = PriceGroup
        extra_kwargs = {
            "publisher": {"required": True, "allow_null": False},
        }


class WebStoreWebhookBaseSerializer(serializers.Serializer):
    order_id = serializers.UUIDField(write_only=True)
    namespace = serializers.ChoiceField(
        choices=[settings.WEB_STORE_API_NAMESPACE],
        write_only=True,
    )


class WebStoreOrderWebhookSerializer(WebStoreWebhookBaseSerializer):
    event_type = serializers.ChoiceField(
        choices=[event_type.value for event_type in WebStoreOrderWebhookEventType],
        write_only=True,
    )


class WebStorePaymentWebhookSerializer(WebStoreWebhookBaseSerializer):
    event_type = serializers.ChoiceField(
        choices=[event_type.value for event_type in WebStorePaymentWebhookEventType],
        write_only=True,
    )


class WebStoreRefundWebhookSerializer(WebStoreWebhookBaseSerializer):
    refund_id = serializers.UUIDField(write_only=True)
    event_type = serializers.ChoiceField(
        choices=[event_type.value for event_type in WebStoreRefundWebhookEventType],
        write_only=True,
    )


class WebStoreMerchantSerializer(CreatedModifiedBaseSerializer):
    admin_only_fields = [
        "paytrail_merchant_id",
        "merchant_id",
    ]

    id = serializers.IntegerField(required=False)

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop("organization", None)

        super().__init__(*args, **kwargs)

        if organization:
            user = self.context["user"]

            if not (
                user.is_authenticated
                and (user.is_superuser or user.is_financial_admin_of(organization))
            ):
                # Show Paytrail and merchant ID fields only to superusers and financial admins.
                for field in self.admin_only_fields:
                    self.fields.pop(field, None)

    class Meta(CreatedModifiedBaseSerializer.Meta):
        model = WebStoreMerchant
        fields = (
            "id",
            "active",
            "name",
            "street_address",
            "zipcode",
            "city",
            "email",
            "phone_number",
            "url",
            "terms_of_service_url",
            "business_id",
            "paytrail_merchant_id",
            "merchant_id",
        ) + CreatedModifiedBaseSerializer.Meta.fields
        extra_kwargs = {
            "merchant_id": {"read_only": True},
            "url": {"read_only": True},
        }
