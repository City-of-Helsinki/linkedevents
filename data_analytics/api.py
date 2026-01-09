import django_filters
from django_orghierarchy.models import Organization
from drf_spectacular.utils import extend_schema, extend_schema_view
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
from data_analytics.openapi import PAGINATION_PARAMS
from data_analytics.serializers import (
    DataAnalyticsAdministrativeDivisionSerializer,
    DataAnalyticsDataSourceSerializer,
    DataAnalyticsEventSerializer,
    DataAnalyticsKeywordSerializer,
    DataAnalyticsLanguageSerializer,
    DataAnalyticsOfferSerializer,
    DataAnalyticsOrganizationSerializer,
    DataAnalyticsPlaceSerializer,
    DataAnalyticsRegistrationSerializer,
    DataAnalyticsSignUpSerializer,
)
from events.models import DataSource, Event, Keyword, Language, Offer, Place
from registrations.models import Registration, SignUp

_ORDER_BY_ID = "-id"
_ORDER_BY_CREATED_TIME = "-created_time"


class DataAnalyticsBaseViewSet(AuditLogApiViewMixin, viewsets.ReadOnlyModelViewSet):
    """Base viewset for data analytics endpoints with Knox authentication."""

    authentication_classes = [KnoxTokenAuthentication]
    http_method_names = ["get", "options"]
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(
        summary="List administrative divisions",
        description=(
            "Retrieve a list of administrative divisions for data analytics purposes."
        ),
        parameters=PAGINATION_PARAMS,
    ),
    retrieve=extend_schema(
        summary="Retrieve administrative division",
        description=(
            "Get detailed information about a specific administrative division."
        ),
    ),
)
class AdministrativeDivisionViewSet(DataAnalyticsBaseViewSet):
    queryset = AdministrativeDivision.objects.order_by(_ORDER_BY_ID)
    serializer_class = DataAnalyticsAdministrativeDivisionSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsAdministrativeDivisionFilter


@extend_schema_view(
    list=extend_schema(
        summary="List data sources",
        description="Retrieve a list of data sources for data analytics purposes.",
        parameters=PAGINATION_PARAMS,
    ),
    retrieve=extend_schema(
        summary="Retrieve data source",
        description="Get detailed information about a specific data source.",
    ),
)
class DataSourceViewSet(DataAnalyticsBaseViewSet):
    queryset = DataSource.objects.order_by(_ORDER_BY_ID)
    serializer_class = DataAnalyticsDataSourceSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List events",
        description="Retrieve a list of events for data analytics purposes.",
        parameters=PAGINATION_PARAMS,
    ),
    retrieve=extend_schema(
        summary="Retrieve event",
        description="Get detailed information about a specific event.",
    ),
)
class EventViewSet(DataAnalyticsBaseViewSet):
    queryset = Event.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsEventSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsEventFilter


@extend_schema_view(
    list=extend_schema(
        summary="List keywords",
        description="Retrieve a list of keywords for data analytics purposes.",
        parameters=PAGINATION_PARAMS,
    ),
    retrieve=extend_schema(
        summary="Retrieve keyword",
        description="Get detailed information about a specific keyword.",
    ),
)
class KeywordViewSet(DataAnalyticsBaseViewSet):
    queryset = Keyword.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsKeywordSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsKeywordFilter


@extend_schema_view(
    list=extend_schema(
        summary="List languages",
        description="Retrieve a list of languages for data analytics purposes.",
        parameters=PAGINATION_PARAMS,
    ),
    retrieve=extend_schema(
        summary="Retrieve language",
        description="Get detailed information about a specific language.",
    ),
)
class LanguageViewSet(DataAnalyticsBaseViewSet):
    queryset = Language.objects.order_by(_ORDER_BY_ID)
    serializer_class = DataAnalyticsLanguageSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List offers",
        description="Retrieve a list of offers for data analytics purposes.",
        parameters=PAGINATION_PARAMS,
    ),
    retrieve=extend_schema(
        summary="Retrieve offer",
        description="Get detailed information about a specific offer.",
    ),
)
class OfferViewSet(DataAnalyticsBaseViewSet):
    queryset = Offer.objects.order_by(_ORDER_BY_ID)
    serializer_class = DataAnalyticsOfferSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List organizations",
        description="Retrieve a list of organizations for data analytics purposes.",
        parameters=PAGINATION_PARAMS,
    ),
    retrieve=extend_schema(
        summary="Retrieve organization",
        description="Get detailed information about a specific organization.",
    ),
)
class OrganizationViewSet(DataAnalyticsBaseViewSet):
    queryset = Organization.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsOrganizationSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsOrganizationFilter


@extend_schema_view(
    list=extend_schema(
        summary="List places",
        description="Retrieve a list of places for data analytics purposes.",
        parameters=PAGINATION_PARAMS,
    ),
    retrieve=extend_schema(
        summary="Retrieve place",
        description="Get detailed information about a specific place.",
    ),
)
class PlaceViewSet(DataAnalyticsBaseViewSet):
    queryset = Place.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsPlaceSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsPlaceFilter


@extend_schema_view(
    list=extend_schema(
        summary="List registrations",
        description="Retrieve a list of registrations for data analytics purposes.",
        parameters=PAGINATION_PARAMS,
    ),
    retrieve=extend_schema(
        summary="Retrieve registration",
        description="Get detailed information about a specific registration.",
    ),
)
class RegistrationViewSet(DataAnalyticsBaseViewSet):
    queryset = Registration.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsRegistrationSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsRegistrationFilter


@extend_schema_view(
    list=extend_schema(
        summary="List signups",
        description="Retrieve a list of signups for data analytics purposes.",
        parameters=PAGINATION_PARAMS,
    ),
    retrieve=extend_schema(
        summary="Retrieve signup",
        description="Get detailed information about a specific signup.",
    ),
)
class SignUpViewSet(DataAnalyticsBaseViewSet):
    queryset = SignUp.objects.order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsSignUpSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DataAnalyticsSignUpFilter
