from datetime import timedelta

import pytz
from django.utils.timezone import localdate, localtime
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.fields import DateTimeField

from events.models import Language
from events.utils import clean_text_fields
from registrations.exceptions import ConflictException
from registrations.models import (
    Registration,
    RegistrationUserAccess,
    SeatReservationCode,
    SignUp,
    SignUpContactPerson,
    SignUpGroup,
    SignUpGroupProtectedData,
    SignUpNotificationType,
    SignUpProtectedData,
)
from registrations.permissions import CanAccessRegistrationSignups
from registrations.utils import code_validity_duration


def _validate_registration_enrolment_times(registration: Registration) -> None:
    enrolment_start_time = registration.enrolment_start_time
    enrolment_end_time = registration.enrolment_end_time
    current_time = localtime()

    if enrolment_start_time and current_time < enrolment_start_time:
        raise ConflictException(_("Enrolment is not yet open."))
    if enrolment_end_time and current_time > enrolment_end_time:
        raise ConflictException(_("Enrolment is already closed."))


def _validate_registration_capacity(
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


class SignUpSerializer(CreatedModifiedBaseSerializer):
    view_name = "signup"
    id = serializers.IntegerField(required=False)
    contact_person = SignUpContactPersonSerializer(required=False, allow_null=True)
    extra_info = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

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

    def create(self, validated_data):
        registration = validated_data["registration"]
        protected_data = _get_protected_data(
            validated_data, ["extra_info", "date_of_birth"]
        )
        contact_person_data = validated_data.pop("contact_person", None) or {}

        add_as_attending, add_as_waitlisted = _validate_registration_capacity(
            registration, 1
        )

        if add_as_attending:
            signup = super().create(validated_data)
            self._update_or_create_protected_data(signup, **protected_data)

            contact_person = self._update_or_create_contact_person(
                signup, **contact_person_data
            )
            if contact_person:
                contact_person.send_notification(SignUpNotificationType.CONFIRMATION)

            return signup
        elif add_as_waitlisted:
            validated_data["attendee_status"] = SignUp.AttendeeStatus.WAITING_LIST

            signup = super().create(validated_data)
            self._update_or_create_protected_data(signup, **protected_data)

            contact_person = self._update_or_create_contact_person(
                signup, **contact_person_data
            )
            if contact_person:
                contact_person.send_notification(
                    SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST
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

        super().update(instance, validated_data)
        self._update_or_create_protected_data(instance, **protected_data)

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
        errors = {}

        if isinstance(self.instance, SignUp):
            registration = self.instance.registration
        else:
            registration = data["registration"]

        falsy_values = ("", None)

        # Validate mandatory fields
        for field in registration.mandatory_fields:
            # Don't validate field if request method is PATCH and field is missing from the payload
            if self.partial and field not in data.keys():
                continue
            elif data.get(field) in falsy_values:
                errors[field] = _("This field must be specified.")

        # Validate date_of_birth if audience_min_age or registration.audience_max_age is defined
        # Don't validate date_of_birth if request method is PATCH and field is missing from the payload
        if (
            registration.audience_min_age not in falsy_values
            or registration.audience_max_age not in falsy_values
        ) and not (self.partial and "date_of_birth" not in data.keys()):
            date_of_birth = data.get("date_of_birth")

            if date_of_birth in falsy_values:
                errors["date_of_birth"] = _("This field must be specified.")
            else:
                today = localdate()
                current_age = (
                    today.year
                    - date_of_birth.year
                    - (
                        (today.month, today.day)
                        < (date_of_birth.month, date_of_birth.year)
                    )
                )
                if (
                    registration.audience_min_age
                    and current_age < registration.audience_min_age
                ):
                    errors["date_of_birth"] = _("The participant is too young.")
                elif (
                    registration.audience_max_age
                    and current_age > registration.audience_max_age
                ):
                    errors["date_of_birth"] = _("The participant is too old.")

        if errors:
            raise serializers.ValidationError(errors)

        super().validate(data)
        return data

    class Meta:
        fields = (
            "id",
            "created_time",
            "last_modified_time",
            "created_by",
            "last_modified_by",
            "first_name",
            "last_name",
            "date_of_birth",
            "city",
            "extra_info",
            "attendee_status",
            "street_address",
            "zipcode",
            "presence_status",
            "registration",
            "signup_group",
            "user_consent",
            "is_created_by_current_user",
            "contact_person",
        )
        model = SignUp


class RegistrationUserAccessIdField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        registration_id = self.context["request"].parser_context["kwargs"]["pk"]
        return RegistrationUserAccess.objects.filter(registration__pk=registration_id)


class RegistrationUserAccessSerializer(serializers.ModelSerializer):
    id = RegistrationUserAccessIdField(required=False, allow_null=True)

    language = serializers.PrimaryKeyRelatedField(
        queryset=Language.objects.filter(service_language=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = RegistrationUserAccess
        fields = ["id", "email", "language"]


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

    registration_user_accesses = RegistrationUserAccessSerializer(
        many=True, required=False
    )

    def get_has_registration_user_access(self, obj):
        user = self.user
        return (
            user.is_authenticated
            and user.is_strongly_identified
            and obj.registration_user_accesses.filter(email=user.email).exists()
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
        return obj.remaining_attendee_capacity

    def get_remaining_waiting_list_capacity(self, obj):
        return obj.remaining_waiting_list_capacity

    def get_data_source(self, obj):
        return obj.data_source.id

    def get_publisher(self, obj):
        return obj.publisher.id

    class Meta:
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
            "created_time",
            "last_modified_time",
            "created_by",
            "last_modified_by",
            "event",
            "created_time",
            "last_modified_time",
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
            "is_created_by_current_user",
        )
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

        if len(data["signups"]) > reservation.seats:
            raise serializers.ValidationError(
                {"signups": "Number of signups exceeds the number of requested seats"}
            )
        data = super().validate(data)
        return data

    @staticmethod
    def _notify_contact_person(contact_person, attendee_status):
        if not contact_person:
            return

        confirmation_type_mapping = {
            SignUp.AttendeeStatus.ATTENDING: SignUpNotificationType.CONFIRMATION,
            SignUp.AttendeeStatus.WAITING_LIST: SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST,
        }

        contact_person.send_notification(confirmation_type_mapping[attendee_status])

    def notify_contact_persons(self, signup_instances):
        for signup in signup_instances:
            if signup.signup_group_id:
                continue

            contact_person = getattr(signup, "contact_person", None)
            self._notify_contact_person(contact_person, signup.attendee_status)

    def create_signups(self, validated_data):
        user = self.context["request"].user
        registration = validated_data["registration"]

        add_as_attending, add_as_waitlisted = _validate_registration_capacity(
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

            signup = SignUp(**cleaned_signup_data)
            signup._extra_info = extra_info
            signup._date_of_birth = date_of_birth
            signup._contact_person = contact_person
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

        return signup_instances


class SignUpGroupCreateSerializer(
    CreatedModifiedBaseSerializer, CreateSignUpsSerializer
):
    reservation_code = serializers.CharField(write_only=True)
    contact_person = SignUpContactPersonSerializer(required=True)
    extra_info = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        # Clean html tags from the text fields
        data = clean_text_fields(data, strip=True)
        validated_data = super().validate(data)

        errors = {}

        if not validated_data.get("contact_person"):
            # The field can be given as an empty dict even if it's required
            # => need to validate this here.
            errors["contact_person"] = _(
                "Contact person information must be provided for a group."
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

    def _create_signups(self, instance, validated_signups_data):
        for signup_data in validated_signups_data:
            signup_data["signup_group"] = instance
            signup_serializer = SignUpSerializer(data=signup_data, context=self.context)
            signup_serializer.create(signup_data)

    def create(self, validated_data):
        validated_data.pop("reservation_code")
        reservation = validated_data.pop("reservation")
        signups_data = validated_data.pop("signups")
        protected_data = _get_protected_data(validated_data, ["extra_info"])
        contact_person_data = validated_data.pop("contact_person")

        instance = super().create(validated_data)
        self._create_protected_data(instance, **protected_data)

        for signup in signups_data:
            signup["signup_group"] = instance
        validated_data["signups"] = signups_data
        self.create_signups(validated_data)

        contact_person = self._create_contact_person(instance, **contact_person_data)
        self._notify_contact_person(
            contact_person,
            SignUp.AttendeeStatus.ATTENDING
            if instance.attending_signups
            else SignUp.AttendeeStatus.WAITING_LIST,
        )

        reservation.delete()

        return instance

    class Meta:
        fields = (
            "id",
            "registration",
            "reservation_code",
            "signups",
            "contact_person",
            "extra_info",
            "created_time",
            "last_modified_time",
            "created_by",
            "last_modified_by",
            "is_created_by_current_user",
        )
        model = SignUpGroup


class SignUpGroupSerializer(CreatedModifiedBaseSerializer):
    view_name = "signupgroup-detail"
    contact_person = SignUpContactPersonSerializer(required=False, allow_null=True)
    extra_info = serializers.CharField(required=False, allow_blank=True)

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

    class Meta:
        fields = (
            "id",
            "registration",
            "signups",
            "contact_person",
            "extra_info",
            "created_time",
            "last_modified_time",
            "created_by",
            "last_modified_by",
            "is_created_by_current_user",
        )
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
