import logging
from typing import Optional, Union

import bleach
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.utils import translation
from django.utils.timezone import localtime
from django.utils.translation import gettext as _
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

from audit_log.mixins import AuditLogApiViewMixin
from events.api import (
    _filter_event_queryset,
    JSONAPIViewMixin,
    RegistrationSerializer,
    UserDataSourceAndOrganizationMixin,
)
from events.models import Event
from events.permissions import OrganizationUserEditPermission
from linkedevents.registry import register_view
from registrations.auth import WebStoreWebhookAuthentication
from registrations.exceptions import (
    ConflictException,
    PriceGroupValidationError,
    WebStoreAPIError,
    WebStoreProductMappingValidationError,
    WebStoreRefundValidationError,
)
from registrations.exports import RegistrationSignUpsExportXLSX
from registrations.filters import (
    ActionDependingBackend,
    PriceGroupFilter,
    SignUpFilter,
    SignUpGroupFilter,
)
from registrations.models import (
    PriceGroup,
    Registration,
    RegistrationUserAccess,
    SeatReservationCode,
    SignUp,
    SignUpGroup,
    SignUpPayment,
    SignUpPaymentRefund,
    SignUpPriceGroup,
)
from registrations.notifications import SignUpNotificationType
from registrations.permissions import (
    CanAccessPriceGroups,
    CanAccessRegistration,
    CanAccessRegistrationSignups,
    CanAccessSignup,
    CanAccessSignupGroup,
)
from registrations.serializers import (
    CreateSignUpsSerializer,
    MassEmailSerializer,
    PriceGroupSerializer,
    RegistrationSignupsExportSerializer,
    RegistrationUserAccessSerializer,
    SeatReservationCodeSerializer,
    SignUpGroupCreateSerializer,
    SignUpGroupSerializer,
    SignUpSerializer,
    WebStoreOrderWebhookSerializer,
    WebStorePaymentWebhookSerializer,
    WebStoreRefundWebhookSerializer,
)
from registrations.utils import (
    get_access_code_for_contact_person,
    get_web_store_order_status,
    get_web_store_payment_status,
    get_web_store_refund_payment_status,
    send_mass_html_mail,
)
from web_store.order.enums import (
    WebStoreOrderRefundStatus,
    WebStoreOrderStatus,
    WebStoreOrderWebhookEventType,
    WebStoreRefundWebhookEventType,
)
from web_store.payment.enums import (
    WebStorePaymentStatus,
    WebStorePaymentWebhookEventType,
)

logger = logging.getLogger(__name__)


class RegistrationsAllowedMethodsMixin:
    http_method_names = ["post", "put", "patch", "get", "delete", "options"]


class SignUpAccessCodeMixin:
    @transaction.atomic
    def retrieve(self, request, *args, **kwargs):
        if request.GET.get("access_code"):
            contact_person = self.get_object().actual_contact_person

            if contact_person and contact_person.check_access_code(
                request.GET.get("access_code")
            ):
                contact_person.link_user(self.request.user)

        return super().retrieve(request, *args, **kwargs)


class SignUpPaymentRefundMixin:
    @transaction.atomic
    def perform_destroy(self, instance):
        if settings.WEB_STORE_INTEGRATION_ENABLED and (
            getattr(instance, "payment_refund", None)
            or getattr(instance, "payment_cancellation", None)
        ):
            raise ConflictException(
                _(
                    "Refund or cancellation already exists. Please wait for the process "
                    "to complete."
                )
            )

        if (
            not (
                self.request.user.is_superuser
                or self.request.user.is_registration_admin_of(instance.publisher)
                or (
                    self.request.user.is_admin_of(instance.publisher)
                    and instance.registration.created_by_id == self.request.user.id
                )
                or self.request.user.is_substitute_user_of(
                    instance.registration.registration_user_accesses
                )
            )
            and instance.registration.event.start_time
            and localtime() > instance.registration.event.start_time
        ):
            raise ConflictException(
                _("Only an admin can delete a signup after an event has started.")
            )

        try:
            super().perform_destroy(instance)
        except (WebStoreAPIError, WebStoreRefundValidationError) as exc:
            raise ValidationError(exc.messages)


class RegistrationViewSet(
    UserDataSourceAndOrganizationMixin,
    JSONAPIViewMixin,
    RegistrationsAllowedMethodsMixin,
    AuditLogApiViewMixin,
    viewsets.ModelViewSet,
):
    serializer_class = RegistrationSerializer
    queryset = Registration.objects.all()

    permission_classes = [CanAccessRegistration]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # user registration admin ids must be injected to the context for nested serializers, to avoid duplicating work
        user = context["request"].user
        registration_admin_tree_ids = set()

        if user and user.is_authenticated:
            registration_admin_tree_ids = user.get_registration_admin_tree_ids()

        context["registration_admin_tree_ids"] = registration_admin_tree_ids
        return context

    @transaction.atomic
    def perform_create(self, serializer):
        try:
            super().perform_create(serializer)
        except (WebStoreAPIError, WebStoreProductMappingValidationError) as exc:
            raise ValidationError(exc.messages)

    @transaction.atomic
    def perform_update(self, serializer):
        try:
            super().perform_update(serializer)
        except (WebStoreAPIError, WebStoreProductMappingValidationError) as exc:
            raise ValidationError(exc.messages)

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
                events = self.request.user.get_editable_events_for_registration(events)
        registrations = Registration.objects.filter(event__in=events)

        return registrations

    def get_serializer_class(self):
        if self.action == "send_message":
            return MassEmailSerializer
        elif self.action == "signups_export":
            return RegistrationSignupsExportSerializer
        return super().get_serializer_class()

    @staticmethod
    def _get_message_contact_persons(signups, signup_groups):
        message_contact_persons = []

        # Make personal email for each signup groups' contact_persons.
        for signup_group in signup_groups:
            if (
                signup_group.attending_signups
                and signup_group.contact_person
                and signup_group.contact_person.email
            ):
                message_contact_persons.append(signup_group.contact_person)

        # Make personal email for each contact_person that is not part of a group.
        for signup in signups:
            if signup.contact_person and signup.contact_person.email:
                message_contact_persons.append(signup.contact_person)

        return message_contact_persons

    @staticmethod
    def _get_messages(subject, cleaned_body, plain_text_body, contact_persons):
        messages = []

        for contact_person in contact_persons:
            message = contact_person.get_registration_message(
                subject, cleaned_body, plain_text_body
            )
            messages.append(message)

        return messages

    @action(
        methods=["post"],
        detail=True,
        permission_classes=[CanAccessRegistration],
    )
    def send_message(self, request, pk=None, version=None):
        registration = self.get_object(skip_log_ids=True)

        signups_perm = CanAccessRegistrationSignups()
        if not signups_perm.has_object_permission(self.request, self, registration):
            raise DRFPermissionDenied(
                _(
                    "Only the admins of the registration organizations have access rights."
                )
            )

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
            signup_groups = registration.signup_groups.filter(
                contact_person__email__isnull=False
            )
            signups = registration.signups.filter(
                contact_person__email__isnull=False,
                attendee_status=SignUp.AttendeeStatus.ATTENDING,
            )

        message_contact_persons = self._get_message_contact_persons(
            signups, signup_groups
        )
        if not message_contact_persons:
            return Response(
                _(
                    "No contact persons with email addresses found for the given participants."
                ),
                status=status.HTTP_404_NOT_FOUND,
            )

        messages = self._get_messages(
            subject, cleaned_body, plain_text_body, message_contact_persons
        )
        send_mass_html_mail(messages, fail_silently=False)

        self._add_audit_logged_object_ids(message_contact_persons)

        return Response(
            {
                "html_message": cleaned_body,
                "message": plain_text_body,
                "signups": [
                    contact_person.signup_id
                    for contact_person in message_contact_persons
                    if contact_person.signup_id
                ],
                "signup_groups": [
                    contact_person.signup_group_id
                    for contact_person in message_contact_persons
                    if contact_person.signup_group_id
                ],
                "subject": subject,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        methods=["get"],
        detail=True,
        permission_classes=[CanAccessRegistrationSignups],
        url_path=r"signups/export/(?P<file_format>xlsx)",
    )
    def signups_export(self, request, file_format=None, pk=None, version=None):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        ui_language = serializer.validated_data["ui_language"]
        registration = self.get_object(skip_log_ids=True)

        with translation.override(ui_language):
            xlsx_export = RegistrationSignUpsExportXLSX(registration)
            xlsx = xlsx_export.get_xlsx()

        response = HttpResponse(
            xlsx,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": 'attachment; filename="registered_persons.xlsx"'
            },
        )

        self._add_audit_logged_object_ids(registration.signups.all().only("pk"))

        return response


register_view(RegistrationViewSet, "registration")


class RegistrationUserAccessViewSet(AuditLogApiViewMixin, viewsets.GenericViewSet):
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


class SignUpViewSet(
    UserDataSourceAndOrganizationMixin,
    RegistrationsAllowedMethodsMixin,
    SignUpAccessCodeMixin,
    SignUpPaymentRefundMixin,
    AuditLogApiViewMixin,
    viewsets.ModelViewSet,
):
    serializer_class = SignUpSerializer
    queryset = SignUp.objects.all()
    filter_backends = [
        ActionDependingBackend,
        filters.OrderingFilter,
    ]
    ordering_fields = ("first_name", "last_name")
    ordering = ("first_name", "last_name")
    filterset_class = SignUpFilter
    permission_classes = [CanAccessSignup]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        context = super().get_serializer_context()
        data = request.data

        if registration_id := data.get("registration"):
            for i in data["signups"]:
                i["registration"] = registration_id

        serializer = CreateSignUpsSerializer(data=data, context=context)
        serializer.is_valid(raise_exception=True)

        signup_with_payment = next(
            (signup for signup in data["signups"] if signup.get("create_payment")), None
        )
        if settings.WEB_STORE_INTEGRATION_ENABLED and signup_with_payment:
            signup_serializer = SignUpSerializer(
                data=signup_with_payment, context=context
            )
            signup_serializer.is_valid(raise_exception=True)
            signup_instances = [
                signup_serializer.create(signup_serializer.validated_data)
            ]
        else:
            signup_instances = serializer.create_signups(serializer.validated_data)
            serializer.notify_contact_persons(signup_instances)

        # Delete reservation
        reservation = serializer.validated_data["reservation"]
        reservation.delete()

        self._add_audit_logged_object_ids(signup_instances)

        return Response(
            data=SignUpSerializer(signup_instances, many=True, context=context).data,
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def perform_update(self, serializer):
        super().perform_update(serializer)

    @transaction.atomic
    def perform_destroy(self, instance):
        instance._individually_deleted = True
        super().perform_destroy(instance)

    @action(
        methods=["delete"],
        detail=True,
        permission_classes=[CanAccessSignup],
    )
    def price_group(self, request, pk=None, version=None):
        if not settings.WEB_STORE_INTEGRATION_ENABLED:
            return Response(
                status=status.HTTP_404_NOT_FOUND,
            )

        price_group = SignUpPriceGroup.objects.filter(signup=self.get_object()).first()

        if not price_group:
            return Response(
                _("The signup does not have a price group."),
                status=status.HTTP_404_NOT_FOUND,
            )

        price_group.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


register_view(SignUpViewSet, "signup")


class SignUpGroupViewSet(
    UserDataSourceAndOrganizationMixin,
    RegistrationsAllowedMethodsMixin,
    SignUpAccessCodeMixin,
    SignUpPaymentRefundMixin,
    AuditLogApiViewMixin,
    viewsets.ModelViewSet,
):
    serializer_class = SignUpGroupSerializer
    queryset = SignUpGroup.objects.all()
    filter_backends = [ActionDependingBackend]
    filterset_class = SignUpGroupFilter
    permission_classes = [CanAccessSignupGroup]

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
    AuditLogApiViewMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SeatReservationCodeSerializer
    queryset = SeatReservationCode.objects.all()
    http_method_names = ["post", "put", "options"]
    permission_classes = [IsAuthenticated]


register_view(SeatReservationViewSet, "seats_reservation")


class PriceGroupViewSet(
    UserDataSourceAndOrganizationMixin,
    RegistrationsAllowedMethodsMixin,
    AuditLogApiViewMixin,
    viewsets.ModelViewSet,
):
    serializer_class = PriceGroupSerializer
    queryset = PriceGroup.objects.all()
    filter_backends = [
        ActionDependingBackend,
        filters.OrderingFilter,
    ]
    filterset_class = PriceGroupFilter
    ordering_fields = ("description",)
    ordering = ("description",)
    permission_classes = [CanAccessPriceGroups]

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except PriceGroupValidationError as exc:
            return Response(
                exc.messages,
                status=status.HTTP_400_BAD_REQUEST,
            )

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except PriceGroupValidationError as exc:
            return Response(
                exc.messages,
                status=status.HTTP_400_BAD_REQUEST,
            )


if settings.WEB_STORE_INTEGRATION_ENABLED:
    register_view(PriceGroupViewSet, "price_group")


class WebStoreWebhookBaseViewSet(AuditLogApiViewMixin, viewsets.ViewSet):
    serializer_class = None
    http_method_names = ["post"]
    authentication_classes = [WebStoreWebhookAuthentication]
    permission_classes = [IsAuthenticated]


class WebStorePaymentWebhookViewSet(WebStoreWebhookBaseViewSet):
    @staticmethod
    def _get_payment(order_id: str) -> Optional[SignUpPayment]:
        payment = (
            SignUpPayment.objects.select_for_update()
            .filter(
                external_order_id=order_id,
                status=SignUpPayment.PaymentStatus.CREATED,
            )
            .first()
        )

        if not payment:
            raise NotFound(
                _("Payment not found with order ID %(order_id)s.")
                % {"order_id": order_id}
            )

        return payment

    @staticmethod
    def _get_payment_status_from_web_store_api(order_id: str) -> Optional[str]:
        try:
            return get_web_store_payment_status(order_id)
        except WebStoreAPIError:
            raise ConflictException(_("Could not check payment status from Talpa API."))

    @staticmethod
    def _get_order_status_from_web_store_api(order_id: str) -> Optional[str]:
        try:
            return get_web_store_order_status(order_id)
        except WebStoreAPIError:
            raise ConflictException(_("Could not check order status from Talpa API."))

    @staticmethod
    def _confirm_signup(signup_or_signup_group: Union[SignUp, SignUpGroup]) -> None:
        contact_person = signup_or_signup_group.actual_contact_person
        if not contact_person:
            return

        access_code = get_access_code_for_contact_person(
            contact_person, signup_or_signup_group.created_by
        )
        contact_person.send_notification(
            SignUpNotificationType.CONFIRMATION, access_code=access_code
        )

    @staticmethod
    def _cancel_signup(signup_or_signup_group: Union[SignUp, SignUpGroup]) -> None:
        if isinstance(signup_or_signup_group, SignUp):
            signup_or_signup_group._individually_deleted = True

        signup_or_signup_group.delete(
            bypass_web_store_api_calls=True, payment_cancelled=True
        )

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def order(self, request, pk=None, version=None):
        serializer = WebStoreOrderWebhookSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"/webhook/order/: {serializer.errors}")
            raise ValidationError(serializer.errors)

        payment = self._get_payment(order_id=str(serializer.validated_data["order_id"]))

        if (
            serializer.validated_data["event_type"]
            == WebStoreOrderWebhookEventType.ORDER_CANCELLED.value
        ):
            order_status = self._get_order_status_from_web_store_api(
                payment.external_order_id
            )
            if order_status != WebStoreOrderStatus.CANCELLED.value:
                return Response(
                    _(
                        "Order marked as cancelled in webhook payload, but not in Talpa API."
                    ),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Order cancelled => cancel signup
            # (email notification is sent automatically as a result of that).
            self._cancel_signup(payment.signup_or_signup_group)

        self._add_audit_logged_object_ids(payment)

        return Response(status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def payment(self, request, pk=None, version=None):
        serializer = WebStorePaymentWebhookSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"/webhook/payment/: {serializer.errors}")
            raise ValidationError(serializer.errors)

        payment = self._get_payment(order_id=str(serializer.validated_data["order_id"]))

        if (
            serializer.validated_data["event_type"]
            == WebStorePaymentWebhookEventType.PAYMENT_PAID.value
        ):
            payment_status = self._get_payment_status_from_web_store_api(
                payment.external_order_id
            )
            if payment_status != WebStorePaymentStatus.PAID.value:
                return Response(
                    _(
                        "Payment marked as paid in webhook payload, but not in Talpa API."
                    ),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Paid successfully => send signup confirmation.
            payment.status = SignUpPayment.PaymentStatus.PAID
            payment.save(update_fields=["status", "last_modified_time"])

            self._confirm_signup(payment.signup_or_signup_group)

        self._add_audit_logged_object_ids(payment)

        return Response(status=status.HTTP_200_OK)


class WebStoreRefundWebhookViewSet(WebStoreWebhookBaseViewSet):
    @staticmethod
    def _get_refund(order_id: str, refund_id: str) -> Optional[SignUpPaymentRefund]:
        refund = SignUpPaymentRefund.objects.filter(
            payment__external_order_id=order_id,
            external_refund_id=refund_id,
        ).first()

        if not refund:
            raise NotFound(
                _(
                    "Refund not found with order ID %(order_id)s and refund ID %(refund_id)s."
                )
                % {"order_id": order_id, "refund_id": refund_id}
            )

        return refund

    @staticmethod
    def _get_refund_status_from_web_store_api(order_id: str) -> Optional[str]:
        try:
            return get_web_store_refund_payment_status(order_id=order_id)
        except WebStoreAPIError:
            raise ConflictException(_("Could not check refund status from Talpa API."))

    @staticmethod
    def _cancel_signup_for_refund(refund: SignUpPaymentRefund) -> None:
        signup_or_signup_group = refund.signup_or_signup_group
        payment = refund.payment

        delete_kwargs = {
            "bypass_web_store_api_calls": True,
            "payment_refunded": refund.amount >= payment.amount,
        }

        if isinstance(signup_or_signup_group, SignUp):
            signup_or_signup_group._individually_deleted = True
            delete_kwargs["payment_partially_refunded"] = refund.amount < payment.amount

        signup_or_signup_group.delete(**delete_kwargs)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def refund(self, request, pk=None, version=None):
        serializer = WebStoreRefundWebhookSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"/webhook/refund/: {serializer.errors}")
            raise ValidationError(serializer.errors)

        order_id = str(serializer.validated_data["order_id"])
        refund_id = str(serializer.validated_data["refund_id"])

        refund = self._get_refund(order_id, refund_id)

        if (
            serializer.validated_data["event_type"]
            == WebStoreRefundWebhookEventType.REFUND_PAID.value
        ):
            refund_status = self._get_refund_status_from_web_store_api(order_id)
            if refund_status != WebStoreOrderRefundStatus.PAID_ONLINE.value:
                return Response(
                    _(
                        "Refund marked as paid in webhook payload, but not in Talpa API."
                    ),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            self._add_audit_logged_object_ids(refund)
            self._cancel_signup_for_refund(refund)
        elif (
            serializer.validated_data["event_type"]
            == WebStoreRefundWebhookEventType.REFUND_FAILED.value
        ):
            refund_status = self._get_refund_status_from_web_store_api(order_id)
            if refund_status != WebStoreOrderRefundStatus.CANCELLED.value:
                return Response(
                    _(
                        "Refund marked as failed in webhook payload, but not in Talpa API."
                    ),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            self._add_audit_logged_object_ids(refund)
            refund.delete()
        else:
            self._add_audit_logged_object_ids(refund)

        return Response(status=status.HTTP_200_OK)


if settings.WEB_STORE_INTEGRATION_ENABLED:
    register_view(
        WebStorePaymentWebhookViewSet, "webhook", base_name="payment_webhooks"
    )
    register_view(WebStoreRefundWebhookViewSet, "webhook", base_name="refund_webhooks")
