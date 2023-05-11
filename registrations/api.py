from datetime import datetime, timedelta
from uuid import UUID

import pytz
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.db import models
from django.db.models import ProtectedError, Q, Sum
from django.utils.translation import gettext as _
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated, NotFound, ParseError
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.response import Response

from events.api import (
    _filter_event_queryset,
    JSONAPIViewMixin,
    RegistrationSerializer,
    UserDataSourceAndOrganizationMixin,
)
from events.models import Event
from events.permissions import DataSourceResourceEditPermission
from linkedevents.registry import register_view
from registrations.exceptions import ConflictException
from registrations.models import Registration, SeatReservationCode, SignUp
from registrations.permissions import SignUpPermission
from registrations.serializers import (
    CreateSignUpsSerializer,
    SeatReservationCodeSerializer,
    SignUpSerializer,
)


class RegistrationViewSet(
    UserDataSourceAndOrganizationMixin,
    JSONAPIViewMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = RegistrationSerializer
    queryset = Registration.objects.all()

    permission_classes = [
        DataSourceResourceEditPermission,
    ]

    def perform_create(self, serializer):
        # Check object level permissions for event which has the relevant data_source.
        event = serializer.validated_data.get("event")
        self.check_object_permissions(self.request, event)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        # Check object level permissions for event which has the relevant data_source.
        event = serializer.validated_data.get("event", serializer.instance.event)
        self.check_object_permissions(self.request, event)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        # At the moment ProtecterError is raised only if user tries to remove registration with signups.
        # Add logic to handle protected errors if more proteted fks are added in the future.
        except ProtectedError:
            raise ConflictException(_("Registration with signups cannot be deleted"))

    def filter_queryset(self, queryset):
        events = Event.objects.exclude(registration=None)

        # Copy query_params to get mutable version of it
        query_params = self.request.query_params.copy()
        # By default _filter_event_queryset only returns events with GENERAL type.
        # This causes problem when getting a registration details, so filter registrations
        # by event_type only when explicitly set
        if not query_params.get("event_type"):
            event_types = {k[1].lower(): k[0] for k in Event.TYPE_IDS}
            query_params["event_type"] = ",".join(event_types.keys())

        events = _filter_event_queryset(events, query_params)

        val = self.request.query_params.get("admin_user", None)
        if val and str(val).lower() == "true":
            if isinstance(self.request.user, AnonymousUser):
                events = Event.objects.none()
            else:
                events = self.request.user.get_editable_events(events)
        registrations = Registration.objects.filter(event__in=events)

        return registrations

    @action(methods=["post"], detail=True, permission_classes=[])
    def reserve_seats(self, request, pk=None, version=None):
        def none_to_unlim(val):
            # Null value in the waiting_list_capacity or maximum_attendee_capacity
            # signifies that the amount of seats is unlimited
            if val is None:
                return 10000
            else:
                return val

        registration = self.registration_get(pk=pk)

        waitlist = request.data.get("waitlist", False)
        if waitlist:
            waitlist_seats = none_to_unlim(registration.waiting_list_capacity)
        else:
            waitlist_seats = 0  # if waitlist is False, waiting list is not to be used

        maximum_attendee_capacity = none_to_unlim(
            registration.maximum_attendee_capacity
        )

        seats_capacity = maximum_attendee_capacity + waitlist_seats
        seats_reserved = registration.reservations.filter(
            timestamp__gte=datetime.now()
            - timedelta(minutes=settings.SEAT_RESERVATION_DURATION)
        ).aggregate(seats_sum=(Sum("seats", output_field=models.FloatField())))[
            "seats_sum"
        ]
        if seats_reserved is None:
            seats_reserved = 0
        seats_taken = registration.signups.count()
        seats_available = seats_capacity - (seats_reserved + seats_taken)

        if request.data.get("seats", 0) > seats_available:
            return Response(
                status=status.HTTP_409_CONFLICT, data="Not enough seats available."
            )
        else:
            code = SeatReservationCode()
            code.registration = registration
            code.seats = request.data.get("seats")
            free_seats = maximum_attendee_capacity - registration.signups.count()
            code.save()
            data = SeatReservationCodeSerializer(code).data
            data["seats_at_event"] = (
                min(free_seats, code.seats) if free_seats > 0 else 0
            )
            waitlist_spots = code.seats - data["seats_at_event"]
            data["waitlist_spots"] = waitlist_spots if waitlist_spots else 0

            return Response(data, status=status.HTTP_201_CREATED)

    def registration_get(self, pk):
        try:
            return Registration.objects.get(pk=pk)
        except (ValueError, Registration.DoesNotExist):
            raise NotFound(detail=f"Registration {pk} doesn't exist.")


register_view(RegistrationViewSet, "registration")


class SignUpViewSet(
    UserDataSourceAndOrganizationMixin,
    JSONAPIViewMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SignUpSerializer
    queryset = SignUp.objects.all()

    permission_classes = [
        SignUpPermission,
    ]

    def create(self, request, *args, **kwargs):
        data = request.data
        registration = data.get("registration", None)
        if registration:
            for i in data["signups"]:
                i["registration"] = registration
        serializer = CreateSignUpsSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        attending = []
        waitlisted = []

        # Create SignUps and add persons to correct list
        for i in data["signups"]:
            signup = SignUpSerializer(data=i, many=False)
            signup.is_valid()
            signee = signup.create(validated_data=signup.validated_data)

            if signee.attendee_status == SignUp.AttendeeStatus.ATTENDING:
                attending.append(SignUpSerializer(signee, many=False).data)
            else:
                waitlisted.append(SignUpSerializer(signee, many=False).data)
        data = {
            "attending": {"count": len(attending), "people": attending},
            "waitlisted": {"count": len(waitlisted), "people": waitlisted},
        }

        # Delete reservation
        reservation = serializer.validated_data["reservation"]
        reservation.delete()

        return Response(data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        registration = instance.registration

        response = super().destroy(request, *args, **kwargs)

        # Move first signup from waitlist to attending list
        waitlisted = registration.signups.filter(
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        ).order_by("id")
        if len(waitlisted) > 0:
            first_on_list = waitlisted[0]
            first_on_list.attendee_status = SignUp.AttendeeStatus.ATTENDING
            first_on_list.save()
        return response

    def filter_queryset(self, queryset):
        request = self.request
        user = request.user

        if registration_param := request.query_params.get("registration", None):
            registrations = []
            for pk in registration_param.split(","):
                try:
                    registration = Registration.objects.get(pk=pk)
                except (ValueError, Registration.DoesNotExist):
                    raise ParseError(
                        _("Registration with id {pk} doesn't exist.").format(pk=pk)
                    )

            if not user.is_admin(registration.publisher):
                raise DRFPermissionDenied(
                    _(
                        "Only the admins of the organization {organization} have access rights."
                    ).format(organization=registration.publisher)
                )

            registrations.append(registration)
            queryset = queryset.filter(registration__in=registrations)
        elif self.action == "list":
            raise ParseError(_("Supply registration ids with 'registration='"))

        if text_param := request.query_params.get("text", None):
            queryset = queryset.filter(
                Q(name__icontains=text_param)
                | Q(email__icontains=text_param)
                | Q(extra_info__icontains=text_param)
                | Q(membership_number__icontains=text_param)
                | Q(phone_number__icontains=text_param)
            )

        if status_param := request.query_params.get("attendee_status", None):
            vals = status_param.lower().split(",")
            statuses = {k[1].lower(): k[0] for k in SignUp.ATTENDEE_STATUSES}

            for v in vals:
                if v not in statuses:
                    raise ParseError(
                        _(
                            "attendee_status can take following values: {statuses}, not {val}"
                        ).format(statuses=", ".join(statuses.keys()), val=status_param)
                    )

            queryset = queryset.filter(attendee_status__in=vals)

        return queryset


register_view(SignUpViewSet, "signup")
