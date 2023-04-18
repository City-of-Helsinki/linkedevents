from datetime import date, timedelta

import pytz
from django.contrib.auth.models import AnonymousUser
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.fields import DateTimeField
from rest_framework.permissions import SAFE_METHODS

from events.models import Event
from registrations.models import (
    MandatoryField,
    Registration,
    SeatReservationCode,
    SignUp,
)
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
            raise DRFPermissionDenied("The waiting list is already full")

    def validate(self, data):
        errors = {}
        registration = data["registration"]
        mandatory_fields = {mf.id for mf in registration.mandatory_fields.all()}

        for field in mandatory_fields:
            val = data.get(field)
            if not val:
                errors[field] = _("This field must be specified.")

        if registration.audience_min_age or registration.audience_max_age:
            if "date_of_birth" not in data.keys():
                errors["date_of_birth"] = _("Date of birth must be specified.")
            else:
                date_of_birth = data["date_of_birth"]
                today = date.today()
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


class RegistrationSerializer(serializers.ModelSerializer):
    view_name = "registration-detail"
    signups = serializers.SerializerMethodField()
    current_attendee_count = serializers.SerializerMethodField()
    current_waiting_list_count = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if kwargs["context"]["request"].data.get("event", None):
            event_id = kwargs["context"]["request"].data["event"]
            event = Event.objects.filter(id=event_id).select_related("publisher")
            if len(event) == 0:
                raise DRFPermissionDenied(_("No event with id {event_id}"))
            user = kwargs["context"]["user"]
            if (
                user.is_admin(event[0].publisher)
                or kwargs["context"]["request"].method in SAFE_METHODS
            ):
                pass
            else:
                raise DRFPermissionDenied(_(f"User {user} cannot modify event {event}"))

    def get_signups(self, obj):
        params = self.context["request"].query_params
        if params.get("include", None) == "signups":
            #  only the organization admins should be able to access the signup information
            user = self.context["user"]
            event = obj.event
            if not isinstance(user, AnonymousUser) and user.is_admin(event.publisher):
                queryset = SignUp.objects.filter(registration__id=obj.id)
                return SignUpSerializer(queryset, many=True, read_only=True).data
            else:
                return f"Only the admins of the organization that published the event {event.id} have access rights."
        else:
            return None

    def get_current_attendee_count(self, obj):
        return SignUp.objects.filter(
            registration__id=obj.id, attendee_status=SignUp.AttendeeStatus.ATTENDING
        ).count()

    def get_current_waiting_list_count(self, obj):
        return SignUp.objects.filter(
            registration__id=obj.id, attendee_status=SignUp.AttendeeStatus.WAITING_LIST
        ).count()

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


class MandatoryFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = MandatoryField
        fields = "__all__"
