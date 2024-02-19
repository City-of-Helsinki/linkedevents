from datetime import timedelta
from decimal import Decimal

import pytz
from django.conf import settings
from django.utils.timezone import localdate, localtime
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.fields import DateTimeField

from events.models import Language
from events.utils import clean_text_fields
from linkedevents.serializers import TranslatedModelSerializer
from registrations.exceptions import ConflictException, WebStoreAPIError
from registrations.models import (
    PriceGroup,
    Registration,
    RegistrationPriceGroup,
    RegistrationUserAccess,
    SeatReservationCode,
    SignUp,
    SignUpContactPerson,
    SignUpGroup,
    SignUpGroupProtectedData,
    SignUpNotificationType,
    SignUpPayment,
    SignUpPriceGroup,
    SignUpProtectedData,
)
from registrations.permissions import CanAccessRegistrationSignups
from registrations.utils import (
    code_validity_duration,
    get_signup_create_url,
    has_allowed_substitute_user_email_domain,
)
from web_store.order.enums import WebStoreOrderWebhookEventType
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


def _validate_registration_enrolment_times(registration: Registration) -> None:
    enrolment_start_time = registration.enrolment_start_time
    enrolment_end_time = registration.enrolment_end_time
    current_time = localtime()

    if enrolment_start_time and current_time < enrolment_start_time:
        raise ConflictException(_("Enrolment is not yet open."))
    if enrolment_end_time and current_time > enrolment_end_time:
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


def _validate_attendee_status_for_payment(
    registration: Registration, signups_count: int, errors: dict
) -> None:
    (
        add_as_attending,
        _add_as_waitlisted,
    ) = _get_attending_and_waitlisted_capacities(registration, signups_count)
    if add_as_attending < signups_count:
        errors["create_payment"] = _(
            "A payment can only be added for attending participants."
        )


class CreatedModifiedBaseSerializer(serializers.ModelSerializer):
    created_time = DateTimeField(
        default_timezone=pytz.UTC, required=False, allow_null=True, read_only=True
    )

    last_modified_time = DateTimeField(
        default_timezone=pytz.UTC, required=False, allow_null=True, read_only=True
    )

    created_by = serializers.StringRelatedField(required=False, allow_null=True)
    last_modified_by = serializers.StringRelatedField(required=False, allow_null=True)

    is_created_by_current_user = serializers.SerializerMethodField()

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


class SignUpPriceGroupSerializer(
    TranslatedModelSerializer, serializers.ModelSerializer
):
    id = serializers.IntegerField(required=False)
    registration_price_group = serializers.PrimaryKeyRelatedField(
        queryset=RegistrationPriceGroup.objects.all(),
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

        for lang_field in ("description_fi", "description_sv", "description_en"):
            validated_data[lang_field] = getattr(
                validated_data["registration_price_group"].price_group, lang_field, None
            )

        for field in ("price", "price_without_vat", "vat", "vat_percentage"):
            validated_data[field] = getattr(
                validated_data["registration_price_group"], field
            )

        return data

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
            signup_or_group.create_web_store_payment()
        except WebStoreAPIError as exc:
            raise serializers.ValidationError(exc.messages)

    class Meta:
        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields = ("create_payment", "payment")
        else:
            fields = ()


class SignUpSerializer(SignUpBaseSerializer, WebStorePaymentBaseSerializer):
    view_name = "signup"
    id = serializers.IntegerField(required=False)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    def get_fields(self):
        fields = super().get_fields()

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields["price_group"] = SignUpPriceGroupSerializer(
                required=False, allow_null=True
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

        if not add_as_attending and add_as_waitlisted:
            validated_data["attendee_status"] = SignUp.AttendeeStatus.WAITING_LIST

        if add_as_attending or add_as_waitlisted:
            signup = super().create(validated_data)

            self._update_or_create_protected_data(signup, **protected_data)
            self._update_or_create_price_group(signup, **price_group_data)
            contact_person = self._update_or_create_contact_person(
                signup, **contact_person_data
            )

        if create_payment and signup and not signup.signup_group_id:
            self._create_payment(signup)

        if contact_person and not create_payment:
            access_code = (
                contact_person.create_access_code()
                if contact_person.can_create_access_code(self.context["request"].user)
                else None
            )
            contact_person.send_notification(
                SignUpNotificationType.CONFIRMATION
                if add_as_attending
                else SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST,
                access_code=access_code,
            )

        if signup:
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

    def validate(self, data):
        # Clean html tags from the text fields
        data = clean_text_fields(data, strip=True)

        validated_data = super().validate(data)

        errors = {}

        instance_id = validated_data.get("id", getattr(self.instance, "pk", None))

        if isinstance(self.instance, SignUp):
            registration = self.instance.registration
        else:
            registration = validated_data["registration"]

        falsy_values = ("", None)

        # Validate mandatory fields
        for field in registration.mandatory_fields:
            # Don't validate field if request method is PATCH and field is missing from the payload
            if self.partial and field not in validated_data.keys():
                continue
            elif validated_data.get(field) in falsy_values:
                errors[field] = _("This field must be specified.")

        # Validate date_of_birth if audience_min_age or registration.audience_max_age is defined
        # Don't validate date_of_birth if request method is PATCH and field is missing from the payload
        if (
            registration.audience_min_age not in falsy_values
            or registration.audience_max_age not in falsy_values
        ) and not (self.partial and "date_of_birth" not in validated_data.keys()):
            date_of_birth = validated_data.get("date_of_birth")

            if date_of_birth in falsy_values:
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

                if (
                    registration.audience_min_age
                    and age < registration.audience_min_age
                ):
                    errors["date_of_birth"] = _("The participant is too young.")
                elif (
                    registration.audience_max_age
                    and age > registration.audience_max_age
                ):
                    errors["date_of_birth"] = _("The participant is too old.")

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            price_group = validated_data.get("price_group") or {}
            if not price_group and registration.registration_price_groups.exists():
                errors["price_group"] = _(
                    "Price group selection is mandatory for this registration."
                )

            if (
                price_group.get("id")
                and instance_id
                and registration.signups.exclude(pk=instance_id)
                .filter(price_group=price_group["id"])
                .exists()
            ):
                errors["price_group"] = _(
                    "Price group is already assigned to another participant."
                )

            if (
                price_group
                and price_group["registration_price_group"].registration_id
                != registration.pk
            ):
                errors["price_group"] = _(
                    "Price group is not one of the allowed price groups for this registration."
                )

            if validated_data.get("create_payment"):
                _validate_signups_for_payment([validated_data], errors, "price_group")

                _validate_contact_person_for_payment(
                    validated_data.get("contact_person"), errors
                )

                _validate_attendee_status_for_payment(registration, 1, errors)

        if errors:
            raise serializers.ValidationError(errors)

        return validated_data

    class Meta(SignUpBaseSerializer.Meta, WebStorePaymentBaseSerializer.Meta):
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

        model = SignUp


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


class RegistrationPriceGroupSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    price_group = PriceGroupRelatedField(queryset=PriceGroup.objects.all())
    price = serializers.DecimalField(
        required=False, max_digits=19, decimal_places=2, min_value=0
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
        min_value=0,
        max_value=Decimal("99.99"),
    )

    def validate(self, data):
        validated_data = super().validate(data)

        errors = {}

        vat_percentage = validated_data.get("vat_percentage")
        if vat_percentage not in [
            vat[0] for vat in RegistrationPriceGroup.VAT_PERCENTAGES
        ]:
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
        model = RegistrationPriceGroup
        fields = [
            "id",
            "price_group",
            "price",
            "vat_percentage",
            "price_without_vat",
            "vat",
        ]


# Don't use this serializer directly but use events.api.RegistrationSerializer instead.
# Implement methods to mutate and validate Registration in events.api.RegistrationSerializer
class RegistrationBaseSerializer(CreatedModifiedBaseSerializer):
    view_name = "registration-detail"

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

    def get_fields(self):
        fields = super().get_fields()

        if self.instance is None:
            fields[
                "registration_user_accesses"
            ] = RegistrationUserAccessCreateSerializer(many=True, required=False)
        else:
            fields["registration_user_accesses"] = RegistrationUserAccessSerializer(
                many=True, required=False
            )

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields["registration_price_groups"] = RegistrationPriceGroupSerializer(
                many=True,
                required=False,
            )

        return fields

    def get_has_registration_user_access(self, obj):
        user = self.user

        has_registration_user_access = (
            user.is_authenticated
            and user.is_strongly_identified
            and obj.registration_user_accesses.filter(email=user.email).exists()
        )

        return has_registration_user_access or self.get_has_substitute_user_access(obj)

    def get_has_substitute_user_access(self, obj):
        user = self.user
        return user.is_authenticated and user.is_substitute_user_of(
            obj.registration_user_accesses
        )

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

    def get_current_attendee_count(self, obj):
        return obj.current_attendee_count

    def get_current_waiting_list_count(self, obj):
        return obj.current_waiting_list_count

    def get_remaining_attendee_capacity(self, obj):
        # Because there can be slight delay with capacity calculations in case of seat expiration,
        # calculate the current value on the fly so that front-end gets the most recent information.
        return obj.calculate_remaining_attendee_capacity()

    def get_remaining_waiting_list_capacity(self, obj):
        # Because there can be slight delay with capacity calculations in case of seat expiration,
        # calculate the current value on the fly so that front-end gets the most recent information.
        return obj.calculate_remaining_waiting_list_capacity()

    def get_data_source(self, obj):
        return obj.data_source.id

    def get_publisher(self, obj):
        return obj.publisher.id

    def get_signup_url(self, obj):
        return {lang: get_signup_create_url(obj, lang) for lang in ["en", "fi", "sv"]}

    class Meta(CreatedModifiedBaseSerializer.Meta):
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
            fields += ("registration_price_groups",)

        model = Registration


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

        # Prevent to signup if enrolment is not open.
        # Raises 409 error if enrolment is not open
        _validate_registration_enrolment_times(registration)

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

    @staticmethod
    def _notify_contact_person(contact_person, attendee_status, user):
        if not contact_person:
            return

        confirmation_type_mapping = {
            SignUp.AttendeeStatus.ATTENDING: SignUpNotificationType.CONFIRMATION,
            SignUp.AttendeeStatus.WAITING_LIST: SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST,
        }

        access_code = (
            contact_person.create_access_code()
            if contact_person.can_create_access_code(user)
            else None
        )
        contact_person.send_notification(
            confirmation_type_mapping[attendee_status], access_code=access_code
        )

    def notify_contact_persons(self, signup_instances):
        user = self.context["request"].user

        for signup in signup_instances:
            if signup.signup_group_id:
                continue

            contact_person = getattr(signup, "contact_person", None)
            self._notify_contact_person(contact_person, signup.attendee_status, user)

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
                cleaned_signup_data[
                    "attendee_status"
                ] = SignUp.AttendeeStatus.WAITING_LIST

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

            _validate_attendee_status_for_payment(
                validated_data["registration"],
                len(validated_data["signups"]),
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

        if create_payment:
            self._create_payment(instance)

        if not (create_payment and instance.attending_signups):
            self._notify_contact_person(
                contact_person,
                SignUp.AttendeeStatus.ATTENDING
                if instance.attending_signups
                else SignUp.AttendeeStatus.WAITING_LIST,
                self.context["request"].user,
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


class SignUpGroupSerializer(SignUpBaseSerializer):
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

        fields["signups"] = SignUpSerializer(
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

    class Meta(SignUpBaseSerializer.Meta):
        fields = (
            "id",
            "registration",
            "signups",
            "anonymization_time",
        ) + SignUpBaseSerializer.Meta.fields

        if settings.WEB_STORE_INTEGRATION_ENABLED:
            fields += ("payment",)

        model = SignUpGroup


class SeatReservationCodeSerializer(serializers.ModelSerializer):
    seats = serializers.IntegerField(required=True)

    timestamp = DateTimeField(default_timezone=pytz.UTC, required=False, read_only=True)

    expiration = serializers.SerializerMethodField()

    in_waitlist = serializers.SerializerMethodField()

    def get_expiration(self, obj):
        return obj.expiration

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

    def validate(self, data):
        instance = self.instance
        errors = {}

        if instance:
            # The code must be defined and match instance code when updating existing seats reservation
            if self.initial_data.get("code") is None:
                errors["code"] = ErrorDetail(
                    _("This field must be specified."), code="required"
                )
            elif str(instance.code) != self.initial_data["code"]:
                errors["code"] = _("The value doesn't match.")

            # Raise validation error if reservation code doesn't match
            if errors:
                raise serializers.ValidationError(errors)

        registration = data["registration"]

        # Prevent to reserve seats if enrolment is not open.
        # Raises 409 error if enrolment is not open
        _validate_registration_enrolment_times(registration)

        maximum_group_size = registration.maximum_group_size

        # Validate maximum group size
        if maximum_group_size is not None and data["seats"] > maximum_group_size:
            errors["seats"] = ErrorDetail(
                _(
                    "Amount of seats is greater than maximum group size: {max_group_size}."
                ).format(max_group_size=maximum_group_size),
                code="max_group_size",
            )

        maximum_attendee_capacity = registration.maximum_attendee_capacity
        waiting_list_capacity = registration.waiting_list_capacity

        # Validate attendee capacity only if maximum_attendee_capacity is defined
        if maximum_attendee_capacity is not None:
            attendee_count = registration.current_attendee_count
            attendee_capacity_left = maximum_attendee_capacity - attendee_count

            if instance:
                reserved_seats_amount = max(
                    registration.reserved_seats_amount - instance.seats, 0
                )
            else:
                reserved_seats_amount = registration.reserved_seats_amount

            # Only allow to reserve seats to event if attendee capacity is not used
            if attendee_capacity_left > 0:
                # Prevent to reserve seats if all available seats are already reserved
                if data["seats"] > attendee_capacity_left - reserved_seats_amount:
                    errors["seats"] = _(
                        "Not enough seats available. Capacity left: {capacity_left}."
                    ).format(
                        capacity_left=max(
                            attendee_capacity_left - reserved_seats_amount, 0
                        )
                    )
            # Validate waiting list capacity only if waiting_list_capacity is defined and
            # and all seats in the event are used
            elif waiting_list_capacity is not None:
                waiting_list_count = registration.current_waiting_list_count
                waiting_list_capacity_left = waiting_list_capacity - waiting_list_count

                # Prevent to reserve seats to waiting ist if all available seats in waiting list
                # are already reserved
                if data["seats"] > waiting_list_capacity_left - reserved_seats_amount:
                    errors["seats"] = _(
                        "Not enough capacity in the waiting list. Capacity left: {capacity_left}."
                    ).format(
                        capacity_left=max(
                            waiting_list_capacity_left - reserved_seats_amount, 0
                        )
                    )

        if errors:
            raise serializers.ValidationError(errors)

        return super().validate(data)

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


class RegistrationSignupsExportSerializer(serializers.Serializer):
    ui_language = serializers.ChoiceField(
        choices=["en", "sv", "fi"],
        default="fi",
    )


class PriceGroupSerializer(TranslatedModelSerializer, CreatedModifiedBaseSerializer):
    def _description_is_valid(self, data, validated_data):
        """
        Validates the translated description fields for Finnish, English and Swedish languages.

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

    def validate(self, data):
        # Clean html tags from the text fields
        data = clean_text_fields(data, strip=True)

        validated_data = super().validate(data)

        errors = {}

        if not self._description_is_valid(data, validated_data):
            errors["description"] = _("This field is required.")

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
