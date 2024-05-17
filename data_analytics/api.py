import django_filters
from django_orghierarchy.models import Organization
from knox.auth import TokenAuthentication as KnoxTokenAuthentication
from munigeo.models import AdministrativeDivision
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from audit_log.mixins import AuditLogApiViewMixin
from data_analytics.filters import (
    DataAnalyticsAdministrativeDivisionFilter,
    DataAnalyticsEventFilter,
    DataAnalyticsKeywordFilter,
    DataAnalyticsOrganizationFilter,
    DataAnalyticsPlaceFilter,
    DataAnalyticsRegistrationFilter,
    DataAnalyticsSignUpFilter,
)
from data_analytics.serializers import (
    DataAnalyticsAdministrativeDivisionSerializer,
    DataAnalyticsEventSerializer,
    DataAnalyticsKeywordSerializer,
    DataAnalyticsLanguageSerializer,
    DataAnalyticsOfferSerializer,
    DataAnalyticsOrganizationSerializer,
    DataAnalyticsPlaceSerializer,
    DataAnalyticsRegistrationSerializer,
    DataAnalyticsSignUpSerializer,
)
from events.models import Event, Keyword, Language, Offer, Place
from registrations.models import Registration, SignUp

_ORDER_BY_ID = "-id"
_ORDER_BY_CREATED_TIME = "-created_time"


class DataAnalyticsBaseViewSet(AuditLogApiViewMixin, viewsets.ReadOnlyModelViewSet):
    authentication_classes = [KnoxTokenAuthentication]
    http_method_names = ["get", "options"]
    permission_classes = [IsAuthenticated]


class KeywordViewSet(DataAnalyticsBaseViewSet):
    queryset = Keyword.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsKeywordSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsKeywordFilter


class LanguageViewSet(DataAnalyticsBaseViewSet):
    queryset = Language.objects.order_by(_ORDER_BY_ID)
    serializer_class = DataAnalyticsLanguageSerializer


class AdministrativeDivisionViewSet(DataAnalyticsBaseViewSet):
    queryset = AdministrativeDivision.objects.order_by(_ORDER_BY_ID)
    serializer_class = DataAnalyticsAdministrativeDivisionSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsAdministrativeDivisionFilter


class PlaceViewSet(DataAnalyticsBaseViewSet):
    queryset = Place.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsPlaceSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsPlaceFilter


class OrganizationViewSet(DataAnalyticsBaseViewSet):
    queryset = Organization.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsOrganizationSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsOrganizationFilter


class EventViewSet(DataAnalyticsBaseViewSet):
    queryset = Event.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsEventSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsEventFilter


class OfferViewSet(DataAnalyticsBaseViewSet):
    queryset = Offer.objects.order_by(_ORDER_BY_ID)
    serializer_class = DataAnalyticsOfferSerializer


class RegistrationViewSet(DataAnalyticsBaseViewSet):
    queryset = Registration.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsRegistrationSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsRegistrationFilter


class SignUpViewSet(DataAnalyticsBaseViewSet):
    queryset = SignUp.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsSignUpSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsSignUpFilter
