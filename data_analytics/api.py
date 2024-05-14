from django_orghierarchy.models import Organization
from knox.auth import TokenAuthentication as KnoxTokenAuthentication
from munigeo.models import AdministrativeDivision
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from audit_log.mixins import AuditLogApiViewMixin
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
    queryset = Keyword.objects.all().order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsKeywordSerializer


class LanguageViewSet(DataAnalyticsBaseViewSet):
    queryset = Language.objects.all().order_by(_ORDER_BY_ID)
    serializer_class = DataAnalyticsLanguageSerializer


class AdministrativeDivisionViewSet(DataAnalyticsBaseViewSet):
    queryset = AdministrativeDivision.objects.all().order_by(_ORDER_BY_ID)
    serializer_class = DataAnalyticsAdministrativeDivisionSerializer


class PlaceViewSet(DataAnalyticsBaseViewSet):
    queryset = Place.objects.all().order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsPlaceSerializer


class OrganizationViewSet(DataAnalyticsBaseViewSet):
    queryset = Organization.objects.all().order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsOrganizationSerializer


class EventViewSet(DataAnalyticsBaseViewSet):
    queryset = Event.objects.all().order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsEventSerializer


class OfferViewSet(DataAnalyticsBaseViewSet):
    queryset = Offer.objects.all().order_by(_ORDER_BY_ID)
    serializer_class = DataAnalyticsOfferSerializer


class RegistrationViewSet(DataAnalyticsBaseViewSet):
    queryset = Registration.objects.all().order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsRegistrationSerializer


class SignUpViewSet(DataAnalyticsBaseViewSet):
    queryset = SignUp.objects.all().order_by(_ORDER_BY_CREATED_TIME)
    serializer_class = DataAnalyticsSignUpSerializer
