from datetime import timedelta

import pytz
from django.contrib.auth.models import AnonymousUser
from django.utils.timezone import localdate
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.fields import DateTimeField

from registrations.models import Registration, SeatReservationCode, SignUp
from registrations.utils import code_validity_duration


class SignUpSerializer(serializers.ModelSerializer):
    view_name = "signup"

    def create(self, validated_data):
        registration = validated_data["registration"]
        already_attending = SignUp.objects.filter(
            registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
        ).count()
        already_waitlisted = SignUp.objects.filter(
            registration=registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        ).count()
        attendee_capacity = registration.maximum_attendee_capacity
        waiting_list_capacity = registration.waiting_list_capacity

        if (attendee_capacity is None) or (already_attending < attendee_capacity):
            signup = super().create(validated_data)
            signup.send_notification("confirmation")
            return signup
        elif (waiting_list_capacity is None) or (
            already_waitlisted < waiting_list_capacity
        ):
            signup = super().create(validated_data)
            signup.attendee_status = SignUp.AttendeeStatus.WAITING_LIST
            signup.save()
            return signup
        else:
            raise DRFPermissionDenied(_("The waiting list is already full"))

    def validate(self, data):
        errors = {}
        registration = data["registration"]
        falsy_values = ("", None)

        for field in registration.mandatory_fields:
            if data.get(field) in falsy_values:
                errors[field] = _("This field must be specified.")

        if (
            registration.audience_min_age not in falsy_values
            or registration.audience_max_age not in falsy_values
        ):
            if "date_of_birth" not in data.keys():
                errors["date_of_birth"] = _("This field must be specified.")
            else:
                date_of_birth = data["date_of_birth"]
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
        fields = "__all__"
        model = SignUp


# Don't use this serializer directly but use events.api.RegistrationSerializer instead.
# Implement methods to mutate and validate Registration in events.api.RegistrationSerializer
class RegistrationBaseSerializer(serializers.ModelSerializer):
    view_name = "registration-detail"

    signups = serializers.SerializerMethodField()

    current_attendee_count = serializers.SerializerMethodField()

    current_waiting_list_count = serializers.SerializerMethodField()

    remaining_attendee_capacity = serializers.SerializerMethodField()

    remaining_waiting_list_capacity = serializers.SerializerMethodField()

    data_source = serializers.SerializerMethodField()

    publisher = serializers.SerializerMethodField()

    created_time = DateTimeField(
        default_timezone=pytz.UTC, required=False, allow_null=True
    )

    last_modified_time = DateTimeField(
        default_timezone=pytz.UTC, required=False, allow_null=True
    )

    created_by = serializers.StringRelatedField(required=False, allow_null=True)

    last_modified_by = serializers.StringRelatedField(required=False, allow_null=True)

    def get_signups(self, obj):
        params = self.context["request"].query_params

        if "signups" in params.get("include", "").split(","):
            #  only the organization admins should be able to access the signup information
            user = self.context["user"]
            event = obj.event
            if not isinstance(user, AnonymousUser) and user.is_admin(event.publisher):
                queryset = SignUp.objects.filter(registration__id=obj.id)
                return SignUpSerializer(queryset, many=True, read_only=True).data
            else:
                return _(
                    "Only the admins of the organization that published the event {event_id} have access rights."
                ).format(event_id=event.id)
        else:
            return None

    def get_current_attendee_count(self, obj):
        return obj.signups.filter(
            attendee_status=SignUp.AttendeeStatus.ATTENDING
        ).count()

    def get_current_waiting_list_count(self, obj):
        return obj.signups.filter(
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST
        ).count()

    def get_remaining_attendee_capacity(self, obj):
        if obj.maximum_attendee_capacity is None:
            return None
        
        maximum_attendee_capacity = obj.maximum_attendee_capacity
        attendee_count = self.get_current_attendee_count(obj)
        reserved_seats_amount = obj.reserved_seats_amount

        return max(
            maximum_attendee_capacity - attendee_count - reserved_seats_amount, 0
        )

    def get_remaining_waiting_list_capacity(self, obj):
        if obj.waiting_list_capacity is None:
            return None

        waiting_list_capacity = obj.waiting_list_capacity
        waiting_list_count = self.get_current_waiting_list_count(obj)
        reserved_seats_amount = obj.reserved_seats_amount

        if obj.maximum_attendee_capacity is not None:
            # Calculate the amount of reserved seats that are used for actual seats 
            # and reduce it from reserved_seats_amount to get amount of reserved seats
            # in the waiting list
            maximum_attendee_capacity = obj.maximum_attendee_capacity
            attendee_count = self.get_current_attendee_count(obj)
            reserved_seats_amount = max(
                reserved_seats_amount
                - max(maximum_attendee_capacity - attendee_count, 0),
                0,
            )

        return max(
            waiting_list_capacity - waiting_list_count - reserved_seats_amount, 0
        )

    def get_data_source(self, obj):
        return obj.data_source.id

    def get_publisher(self, obj):
        return obj.publisher.id

    class Meta:
        fields = "__all__"
        model = Registration


class SeatReservationCodeSerializer(serializers.ModelSerializer):
    timestamp = DateTimeField(default_timezone=pytz.UTC, required=False)
    expiration = serializers.SerializerMethodField()

    class Meta:
        fields = ("seats", "code", "timestamp", "registration", "expiration")
        model = SeatReservationCode

    def get_expiration(self, obj):
        return obj.timestamp + timedelta(minutes=code_validity_duration(obj.seats))


class MassEmailSignupsField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        registration = self.context["request"].data["registration"]

        return registration.signups.exclude(email=None)


class MassEmailSerializer(serializers.Serializer):
    subject = serializers.CharField()
    body = serializers.CharField()
    signups = MassEmailSignupsField(
        many=True,
        required=False,
    )
