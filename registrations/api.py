import logging
from smtplib import SMTPException

import bleach
import django_filters
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import ProtectedError, Q, Value
from django.db.models.functions import Concat
from django.utils.translation import gettext as _
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
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
    OrganizationUserEditPermission,
)
from linkedevents.registry import register_view
from registrations.exceptions import ConflictException
from registrations.models import (
    Registration,
    RegistrationUserAccess,
    SeatReservationCode,
    SignUp,
    SignUpGroup,
)
from registrations.permissions import CanAccessRegistration, CanAccessSignup
from registrations.serializers import (
    CreateSignUpsSerializer,
    MassEmailSerializer,
    RegistrationUserAccessSerializer,
    SeatReservationCodeSerializer,
    SignUpGroupCreateSerializer,
    SignUpGroupSerializer,
    SignUpSerializer,
)
from registrations.utils import send_mass_html_mail

logger = logging.getLogger(__name__)


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

    permission_classes = [CanAccessRegistration & DataSourceResourceEditPermission]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # user registration admin ids must be injected to the context for nested serializers, to avoid duplicating work
        user = context["request"].user
        registration_admin_tree_ids = set()

        if user and user.is_authenticated:
            registration_admin_tree_ids = user.get_registration_admin_tree_ids()

        context["registration_admin_tree_ids"] = registration_admin_tree_ids
        return context

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

    def get_serializer_class(self):
        if self.action == "send_message":
            return MassEmailSerializer
        return super().get_serializer_class()

    @staticmethod
    def _get_messages(subject, cleaned_body, plain_text_body, signups, signup_groups):
        messages = []

        if not (signups or signup_groups):
            return messages

        already_included_signups = set()

        # Make personal email for each signup groups' responsible signups
        for signup_group in signup_groups:
            responsible_signups = (
                signup_group.responsible_signups or signup_group.signups.all()
            )
            for signup in responsible_signups.exclude(email=None):
                message = signup.get_registration_message(
                    subject, cleaned_body, plain_text_body
                )
                messages.append(message)
                already_included_signups.add(signup.pk)

        # Make personal email for each individual signup that
        # was not already processed as part of a group.
        for signup in signups:
            if signup.pk in already_included_signups:
                continue
            message = signup.get_registration_message(
                subject, cleaned_body, plain_text_body
            )
            messages.append(message)

        return messages

    @action(
        methods=["post"],
        detail=True,
        permission_classes=[CanAccessRegistration & DataSourceResourceEditPermission],
    )
    def send_message(self, request, pk=None, version=None):
        registration = self.get_object()

        data = request.data
        data["registration"] = registration
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        body = serializer.validated_data["body"]
        subject = serializer.validated_data["subject"]
        cleaned_body = bleach.clean(
            body.replace("\n", "<br>"), settings.BLEACH_ALLOWED_TAGS
        )
        plain_text_body = bleach.clean(body, strip=True)

        signup_groups = serializer.validated_data.get("signup_groups", [])
        signups = serializer.validated_data.get("signups", [])
        if not (signup_groups or signups):
            signup_groups = registration.signup_groups.all()
            signups = registration.signups.exclude(email=None)
        messages = self._get_messages(
            subject,
            cleaned_body,
            plain_text_body,
            signups,
            signup_groups,
        )
        try:
            send_mass_html_mail(messages, fail_silently=False)
        except SMTPException as e:
            logger.exception("Couldn't send mass HTML email.")

            return Response(
                str(e),
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "html_message": cleaned_body,
                "message": plain_text_body,
                "signups": [su.id for su in signups],
                "subject": subject,
            },
            status=status.HTTP_200_OK,
        )


register_view(RegistrationViewSet, "registration")


class RegistrationUserAccessViewSet(viewsets.GenericViewSet):
    queryset = RegistrationUserAccess.objects.all()
    serializer_class = RegistrationUserAccessSerializer
    permission_classes = [OrganizationUserEditPermission]

    @action(detail=True, methods=["post"])
    def send_invitation(self, request, pk=None, version=None):
        registration_user_access = self.get_object()
        registration_user_access.send_invitation()
        return Response(
            status=status.HTTP_200_OK,
        )


register_view(RegistrationUserAccessViewSet, "registration_user_access")


class SignUpFilterBackend(django_filters.rest_framework.DjangoFilterBackend):
    def get_filterset_kwargs(self, request, queryset, view):
        kwargs = super().get_filterset_kwargs(request, queryset, view)
        kwargs["action"] = view.action

        return kwargs


class SignUpBaseFilter(django_filters.rest_framework.FilterSet):
    registration = django_filters.Filter(
        widget=django_filters.widgets.CSVWidget(),
        method="filter_registration",
    )

    attendee_status = django_filters.MultipleChoiceFilter(
        choices=SignUp.ATTENDEE_STATUSES,
        widget=django_filters.widgets.CSVWidget(),
    )

    text = django_filters.CharFilter(method="filter_text")

    def __init__(self, *args, **kwargs):
        self.action = kwargs.pop("action", None)
        super().__init__(*args, **kwargs)

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)

        user = self.request.user

        if self.action and self.action != "list" or user.is_superuser:
            return queryset

        # By default, return only signups of registrations to which
        # user has admin rights or is registration user who is
        # strongly identified.
        q_filter = Q(
            registration__event__publisher__in=user.get_registration_admin_organizations_and_descendants()
        )
        if user.is_strongly_identificated:
            q_filter |= Q(registration__registration_user_accesses__email=user.email)

        return queryset.filter(q_filter)

    def filter_registration(self, queryset, name, value: list[str]):
        user = self.request.user

        # Get admin organizations and descendants only once instead of using is_admin method
        registration_admin_organizations = (
            user.get_registration_admin_organizations_and_descendants()
        )

        registrations = []
        for pk in value:
            try:
                registration = Registration.objects.select_related(
                    "event__publisher"
                ).get(pk=pk)
            except (ValueError, Registration.DoesNotExist):
                raise ParseError(
                    _("Registration with id {pk} doesn't exist.").format(pk=pk)
                )

            if not (
                user.is_superuser
                or user.is_registration_user_access_user_of(
                    registration.registration_user_accesses
                )
                or registration.publisher in registration_admin_organizations
            ):
                raise DRFPermissionDenied(
                    _(
                        "Only the admins of the organization {organization} have access rights."
                    ).format(organization=registration.publisher)
                )

            registrations.append(registration)

        return queryset.filter(**{f"{name}__in": registrations})

    @staticmethod
    def _build_text_annotations(relation_accessor=""):
        return {
            f"{relation_accessor}first_last_name": Concat(
                f"{relation_accessor}first_name",
                Value(" "),
                f"{relation_accessor}last_name",
            ),
            f"{relation_accessor}last_first_name": Concat(
                f"{relation_accessor}last_name",
                Value(" "),
                f"{relation_accessor}first_name",
            ),
        }

    @staticmethod
    def _build_text_filter(text_param, relation_accessor=""):
        filters = {
            f"{relation_accessor}first_last_name__icontains": text_param,
            f"{relation_accessor}last_first_name__icontains": text_param,
            f"{relation_accessor}email__icontains": text_param,
            f"{relation_accessor}extra_info__icontains": text_param,
            f"{relation_accessor}membership_number__icontains": text_param,
            f"{relation_accessor}phone_number__icontains": text_param,
        }

        q_set = Q()
        for item in filters.items():
            q_set |= Q(item)

        return q_set

    def filter_text(self, queryset, name, value):
        return queryset.annotate(**self._build_text_annotations()).filter(
            self._build_text_filter(value)
        )


class SignUpFilter(SignUpBaseFilter):
    class Meta:
        model = SignUp
        fields = ("registration", "attendee_status")


class SignUpGroupFilter(SignUpBaseFilter):
    attendee_status = django_filters.MultipleChoiceFilter(
        field_name="signups__attendee_status",
        choices=SignUp.ATTENDEE_STATUSES,
        widget=django_filters.widgets.CSVWidget(),
    )

    def filter_text(self, queryset, name, value):
        return queryset.annotate(
            **self._build_text_annotations(relation_accessor="signups__")
        ).filter(self._build_text_filter(value, relation_accessor="signups__"))

    class Meta:
        model = SignUpGroup
        fields = ("registration",)


class SignUpViewSet(
    UserDataSourceAndOrganizationMixin,
    viewsets.ModelViewSet,
):
    serializer_class = SignUpSerializer
    queryset = SignUp.objects.all()
    filter_backends = [SignUpFilterBackend]
    filterset_class = SignUpFilter
    permission_classes = [CanAccessSignup & DataSourceResourceEditPermission]

    def create(self, request, *args, **kwargs):
        context = super().get_serializer_context()
        data = request.data
        registration = data.get("registration", None)
        if registration:
            for i in data["signups"]:
                i["registration"] = registration
        serializer = CreateSignUpsSerializer(data=data, context=context)
        serializer.is_valid(raise_exception=True)

        attending = []
        waitlisted = []

        # Create SignUps and add persons to correct list
        for i in data["signups"]:
            signup = SignUpSerializer(data=i, context=context)
            signup.is_valid()
            signee = signup.create(validated_data=signup.validated_data)

            if signee.attendee_status == SignUp.AttendeeStatus.ATTENDING:
                attending.append(SignUpSerializer(signee, context=context).data)
            else:
                waitlisted.append(SignUpSerializer(signee, context=context).data)
        data = {
            "attending": {"count": len(attending), "people": attending},
            "waitlisted": {"count": len(waitlisted), "people": waitlisted},
        }

        # Delete reservation
        reservation = serializer.validated_data["reservation"]
        reservation.delete()

        return Response(data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def perform_destroy(self, instance):
        instance._individually_deleted = True
        instance.delete()


register_view(SignUpViewSet, "signup")


class SignUpGroupViewSet(
    UserDataSourceAndOrganizationMixin,
    viewsets.ModelViewSet,
):
    serializer_class = SignUpGroupSerializer
    queryset = SignUpGroup.objects.all()
    filter_backends = [SignUpFilterBackend]
    filterset_class = SignUpGroupFilter
    permission_classes = [CanAccessSignup & DataSourceResourceEditPermission]

    def get_serializer_class(self):
        if self.action == "create":
            return SignUpGroupCreateSerializer
        return super().get_serializer_class()

    def _ensure_shared_request_data(self, data):
        if self.action == "partial_update":
            registration_id = data.get(
                "registration", self.get_object().registration_id
            )
        else:
            registration_id = data.get("registration")

        if not registration_id or not data.get("signups"):
            return

        for signup_data in data["signups"]:
            signup_data["registration"] = registration_id

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        self._ensure_shared_request_data(request.data)
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        self._ensure_shared_request_data(request.data)
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        self._ensure_shared_request_data(request.data)
        return super().partial_update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


register_view(SignUpGroupViewSet, "signup_group")


class SeatReservationViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SeatReservationCodeSerializer
    queryset = SeatReservationCode.objects.all()
    permission_classes = [IsAuthenticated]


register_view(SeatReservationViewSet, "seats_reservation")
