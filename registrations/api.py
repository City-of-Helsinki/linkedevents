import logging
from datetime import datetime, timedelta
from smtplib import SMTPException
from uuid import UUID

import bleach
import pytz
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.db import models
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db.models import ProtectedError, Q, Sum
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from events.api import (
    _filter_event_queryset,
    JSONAPIViewMixin,
    RegistrationSerializer,
    UserDataSourceAndOrganizationMixin,
)
from events.models import Event
from events.permissions import (
    DataSourceResourceEditPermission,
    GuestDelete,
    GuestGet,
    GuestPost,
)
from linkedevents.registry import register_view
from registrations.exceptions import ConflictException
from registrations.models import Registration, SeatReservationCode, SignUp
from registrations.serializers import SeatReservationCodeSerializer, SignUpSerializer
from registrations.utils import code_validity_duration

logger = logging.getLogger(__name__)


class SignUpViewSet(
    JSONAPIViewMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SignUpSerializer
    queryset = SignUp.objects.all()
    permission_classes = [GuestPost | GuestDelete | GuestGet]

    def get_signup_by_code(self, code):
        try:
            UUID(code)
        except ValueError:
            raise DRFPermissionDenied("Malformed UUID.")
        qs = SignUp.objects.filter(cancellation_code=code)
        if qs.count() == 0:
            raise DRFPermissionDenied(
                "Cancellation code did not match any registration"
            )
        return qs[0]

    def get(self, request, *args, **kwargs):
        # First dealing with the cancellation codes
        if isinstance(request.user, AnonymousUser):
            code = request.GET.get("cancellation_code", "no code")
            if code == "no code":
                raise DRFPermissionDenied(
                    "cancellation_code parameter has to be provided"
                )
            signup = self.get_signup_by_code(code)
            return Response(SignUpSerializer(signup).data)
        # Provided user is logged in
        else:
            reg_ids = []
            event_ids = []
            val = request.query_params.get("registrations", None)
            if val:
                reg_ids = val.split(",")
            val = request.query_params.get("events", None)
            if val:
                event_ids = val.split(",")
            qs = Event.objects.filter(
                Q(id__in=event_ids) | Q(registration__id__in=reg_ids)
            )

            if len(reg_ids) == 0 and len(event_ids) == 0:
                qs = Event.objects.exclude(registration=None)
            authorized_events = request.user.get_editable_events(qs)

            signups = SignUp.objects.filter(registration__event__in=authorized_events)

            val = request.query_params.get("text", None)
            if val:
                signups = signups.filter(
                    Q(name__icontains=val)
                    | Q(email__icontains=val)
                    | Q(extra_info__icontains=val)
                    | Q(membership_number__icontains=val)
                    | Q(phone_number__icontains=val)
                )
            val = request.query_params.get("attendee_status", None)
            if val:
                if val in ["waitlisted", "attending"]:
                    signups = signups.filter(attendee_status=val)
                else:
                    raise DRFPermissionDenied(
                        f"attendee_status can take values waitlisted and attending, not {val}"
                    )
            return Response(SignUpSerializer(signups, many=True).data)

    def delete(self, request, *args, **kwargs):
        code = request.data.get("cancellation_code", "no code")
        if code == "no code":
            raise DRFPermissionDenied("cancellation_code parameter has to be provided")
        signup = self.get_signup_by_code(code)
        waitlisted = SignUp.objects.filter(
            registration=signup.registration,
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        ).order_by("id")
        signup.send_notification("cancellation")
        signup.delete()
        if len(waitlisted) > 0:
            first_on_list = waitlisted[0]
            first_on_list.attendee_status = SignUp.AttendeeStatus.ATTENDING
            first_on_list.save()
        return Response("SignUp deleted.", status=status.HTTP_200_OK)


register_view(SignUpViewSet, "signup")


class SignUpEditViewSet(
    JSONAPIViewMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SignUpSerializer
    queryset = SignUp.objects.all()
    permission_classes = (IsAuthenticated,)


register_view(SignUpEditViewSet, "signup_edit")


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

    @action(methods=["post"], detail=True, permission_classes=[GuestPost])
    def reserve_seats(self, request, pk=None, version=None):
        def none_to_unlim(val):
            # Null value in the waiting_list_capacity or maximum_attendee_capacity
            # signifies that the amount of seats is unlimited
            if val is None:
                return 10000
            else:
                return val

        try:
            registration = Registration.objects.get(id=pk)
        except Registration.DoesNotExist:
            raise NotFound(detail=f"Registration {pk} doesn't exist.", code=404)
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

    @action(
        methods=["post"],
        detail=True,
        permission_classes=[DataSourceResourceEditPermission],
    )
    def send_message(self, request, pk=None, version=None):
        def send_mass_html_mail(
            datatuple,
            fail_silently=False,
            auth_user=None,
            auth_password=None,
            connection=None,
        ):
            """
            django.core.mail.send_mass_mail doesn't support sending html mails,

            This method duplicates send_mass_mail except requires html_message for each message
            and adds html alternative to each mail
            """
            connection = connection or get_connection(
                username=auth_user,
                password=auth_password,
                fail_silently=fail_silently,
            )
            messages = []
            for subject, message, html_message, from_email, recipient_list in datatuple:
                mail = EmailMultiAlternatives(
                    subject, message, from_email, recipient_list, connection=connection
                )
                mail.attach_alternative(html_message, "text/html")
                messages.append(mail)

            return connection.send_messages(messages)

        registration = self.get_object()

        errors = {}

        # Validate that required fields are filled
        required_fields = ["subject", "body"]
        for field in required_fields:
            if not request.data.get(field):
                errors[field] = _("This field must be specified.")

        # Send message to defined signups if signups attribute is defined and it's an array
        # By default send message to all signups
        if request.data.get("signups") and hasattr(
            request.data.get("signups"), "__len__"
        ):
            try:
                signups = registration.signups.filter(
                    pk__in=[i for i in request.data.get("signups")]
                )
            except ValueError as error:
                errors["signups"] = str(error)

        else:
            signups = registration.signups.all()
        signups.exclude(email=None)

        # Return validations errors if there is any
        if errors:
            raise serializers.ValidationError(errors)

        messages = []
        subject = request.data["subject"]
        body = request.data["body"]
        cleaned_body = bleach.clean(
            body.replace("\n", "<br>"), settings.BLEACH_ALLOWED_TAGS
        )
        plain_text_body = bleach.clean(body, strip=True)

        # Email contains a link to a signup so make personal email for each signup
        for signup in signups:
            email_variables = {
                "linked_events_ui_url": settings.LINKED_EVENTS_UI_URL,
                "linked_registrations_ui_url": settings.LINKED_REGISTRATIONS_UI_URL,
                "body": cleaned_body,
                "cancellation_code": signup.cancellation_code,
                "registration_id": registration.id,
            }
            rendered_body = render_to_string("message_to_signup.html", email_variables)
            message = (
                subject,
                plain_text_body,
                rendered_body,
                settings.SUPPORT_EMAIL,
                [signup.email],
            )
            messages.append(message)

        try:
            send_mass_html_mail(messages, fail_silently=False)
        except SMTPException as e:
            logger.error(e, exc_info=True)
            return Response(
                str(e),
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "emails": [su.email for su in signups],
                "html_message": cleaned_body,
                "message": plain_text_body,
                "subject": subject,
            },
            status=status.HTTP_200_OK,
        )

    @action(methods=["post"], detail=True, permission_classes=[GuestPost])
    def signup(self, request, pk=None, version=None):
        attending = []
        waitlisted = []
        if "reservation_code" not in request.data.keys():
            raise serializers.ValidationError(
                {"registration": "Reservation code is missing"}
            )

        try:
            reservation = SeatReservationCode.objects.get(
                code=request.data["reservation_code"]
            )
        except SeatReservationCode.DoesNotExist:
            msg = f"Reservation code {request.data['reservation_code']} doesn't exist."
            raise NotFound(detail=msg, code=404)

        if str(reservation.registration.id) != pk:
            msg = f"Registration code {request.data['reservation_code']} doesn't match the registration {pk}"
            raise serializers.ValidationError({"reservation_code": msg})

        if len(request.data["signups"]) > reservation.seats:
            raise serializers.ValidationError(
                {"signups": "Number of signups exceeds the number of requested seats"}
            )

        expiration = reservation.timestamp + timedelta(
            minutes=code_validity_duration(reservation.seats)
        )
        if datetime.now().astimezone(pytz.utc) > expiration:
            raise serializers.ValidationError({"code": "Reservation code has expired."})

        for i in request.data["signups"]:
            i["registration"] = pk

        # First check that all the signups are valid and then actually create them
        for i in request.data["signups"]:
            serializer = SignUpSerializer(data=i)
            if not serializer.is_valid():
                raise serializers.ValidationError(serializer.errors)

        for i in request.data["signups"]:
            signup = SignUpSerializer(data=i, many=False)
            signup.is_valid()
            signee = signup.create(validated_data=signup.validated_data)
            if signee.attendee_status == SignUp.AttendeeStatus.ATTENDING:
                attending.append({"id": signee.id, "name": signee.name})
            else:
                waitlisted.append({"id": signee.id, "name": signee.name})
        reservation.delete()
        data = {
            "attending": {"count": len(attending), "people": attending},
            "waitlisted": {"count": len(waitlisted), "people": waitlisted},
        }

        return Response(data, status=status.HTTP_201_CREATED)


register_view(RegistrationViewSet, "registration")
