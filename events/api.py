import logging
import re
import urllib.parse
from datetime import datetime, timedelta
from datetime import time as datetime_time
from datetime import timezone as datetime_timezone
from functools import partial, reduce
from operator import or_
from typing import Literal, Union

import django_filters
import pytz
import regex
from django.conf import settings
from django.contrib.gis.gdal import GDALException
from django.contrib.postgres.search import SearchQuery, TrigramSimilarity
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, QuerySet
from django.db.models.functions import Greatest
from django.http import Http404, HttpResponsePermanentRedirect
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.functional import cached_property
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization, OrganizationClass
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiRequest,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    inline_serializer,
)
from haystack.query import AutoQuery
from munigeo.api import GeoModelAPIView, build_bbox_filter, srid_to_srs
from munigeo.models import AdministrativeDivision
from rest_framework import (
    filters,
    generics,
    mixins,
    permissions,
    serializers,
    status,
    viewsets,
)
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ParseError, ValidationError
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.filters import BaseFilterBackend
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.settings import api_settings
from rest_framework_bulk import BulkModelViewSet

from audit_log.mixins import AuditLogApiViewMixin
from events import utils
from events.api_pagination import LargeResultsSetPagination
from events.auth import ApiKeyUser
from events.custom_elasticsearch_search_backend import (
    CustomEsSearchQuerySet as SearchQuerySet,
)
from events.extensions import apply_select_and_prefetch, get_extensions_from_request
from events.filters import (
    EventFilter,
    EventOrderingFilter,
    OrganizationFilter,
    PlaceFilter,
    filter_division,
)
from events.models import (
    DataSource,
    Event,
    Image,
    Keyword,
    KeywordSet,
    Language,
    Offer,
    Place,
    PublicationStatus,
)
from events.permissions import (
    DataSourceResourceEditPermission,
    GuestPost,
    GuestRetrieve,
    IsObjectEditableByUser,
    OrganizationEditPermission,
    OrganizationUserEditPermission,
    OrganizationWebStoreMerchantsAndAccountsPermission,
    UserIsAdminInAnyOrganization,
)
from events.renderers import DOCXRenderer
from events.serializers import (
    DataSourceSerializer,
    EventSerializer,
    EventSerializerV0_1,
    FeedbackSerializer,
    ImageSerializer,
    KeywordSerializer,
    KeywordSetSerializer,
    LanguageSerializer,
    OrganizationClassSerializer,
    OrganizationDetailSerializer,
    OrganizationListSerializer,
    PlaceSerializer,
    SearchSerializer,
    SearchSerializerV0_1,
)
from events.translation import EventTranslationOptions, PlaceTranslationOptions
from linkedevents.registry import register_view
from linkedevents.schema_utils import (
    IncludeOpenApiParameter,
    get_common_api_error_responses,
)
from linkedevents.utils import get_fixed_lang_codes
from registrations.exceptions import WebStoreAPIError
from registrations.serializers import (
    WebStoreAccountSerializer,
    WebStoreMerchantSerializer,
)

logger = logging.getLogger(__name__)


class UserDataSourceAndOrganizationMixin:
    def get_serializer_context(self):
        context = super().get_serializer_context()
        (
            context["data_source"],
            context["publisher"],
        ) = self.user_data_source_and_organization
        return context

    @cached_property
    def user_data_source_and_organization(self):
        return utils.get_user_data_source_and_organization_from_request(self.request)


def get_publisher_query(publisher):
    """Get query for publisher (Organization)

    Some organizations can be replaced by a new organization.
    We need to return objects that reference on replaced
    organization when querying the new organization, and vice
    versa.

    :param publisher: a or a list of filtering organizations
    :type publisher: str, Organization, list
    :return: the query that check both replaced and new organization
    """
    if isinstance(publisher, list):
        q = (
            Q(
                publisher__in=publisher,
            )
            | Q(
                publisher__replaced_by__in=publisher,
            )
            | Q(
                publisher__replaced_organization__in=publisher,
            )
        )
    else:
        q = (
            Q(
                publisher=publisher,
            )
            | Q(
                publisher__replaced_by=publisher,
            )
            | Q(
                publisher__replaced_organization=publisher,
            )
        )

    return q


def parse_hours(val, param):
    if len(val) > 2:
        raise ParseError(
            f"Only hours and minutes can be given in {param}. For example: 16:00."
        )
    try:
        hour = int(val[0])
    except ValueError:
        raise ParseError(
            f"Hours should be passed as numbers in {param}. For example: 16:00."
        )
    if not (0 <= hour <= 23):
        raise ParseError(
            f"Hours should be between 0 and 23 in {param}, for example: 16:00. You have passed {hour}."
        )
    if len(val) == 2 and val[1]:
        try:
            minute = int(val[1])
        except ValueError:
            raise ParseError(
                f"Minutes should be passed as numbers in {param}. For example: 16:20."
            )
        if not (0 <= minute <= 59):
            raise ParseError(
                f"Minutes should be between 0 and 59 in {param} as in 16:20. You passed {minute}."
            )
        return hour, minute
    return hour, 0


def parse_bool(val, param):
    if val.lower() == "true":
        return True
    elif val.lower() == "false":
        return False
    else:
        raise ParseError(
            f"{param} can take the values True or False. You passed {val}."
        )


def parse_digit(val, param):
    try:
        return int(val)
    except ValueError:
        raise ParseError(f'{param} must be an integer, you passed "{val}"')


def _text_qset_by_translated_field(field, val):
    # Free text search from all languages of the field
    languages = get_fixed_lang_codes()
    qset = Q()
    for lang in languages:
        kwarg = {field + "_" + lang + "__icontains": val}
        qset |= Q(**kwarg)
    return qset


class JSONAPIViewMixin(object):
    def initial(self, request, *args, **kwargs):
        ret = super().initial(request, *args, **kwargs)
        # if srid is not specified, this will yield munigeo default 4326
        try:
            self.srs = srid_to_srs(self.request.query_params.get("srid", None))
        except GDALException:
            raise ValidationError("Invalid SRID provided.", code=400)

        # check for NUL strings that crash psycopg2
        for _key, param in self.request.query_params.items():
            if "\x00" in param:
                raise ParseError(
                    "A string literal cannot contain NUL (0x00) characters. "
                    "Please fix query parameter " + param
                )
        return ret

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # user admin ids must be injected to the context for nested serializers, to avoid duplicating work
        user = context["request"].user
        admin_tree_ids = set()
        if user and user.is_authenticated:
            admin_tree_ids = user.get_admin_tree_ids()
        context["user"] = user
        context["admin_tree_ids"] = admin_tree_ids
        include = self.request.query_params.get("include", "")
        context["include"] = [x.strip() for x in include.split(",") if x]
        context["srs"] = self.srs
        context.setdefault("skip_fields", set()).add("origin_id")
        return context


class KeywordViewSet(
    UserDataSourceAndOrganizationMixin,
    JSONAPIViewMixin,
    AuditLogApiViewMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Keyword.objects.all()
    queryset = queryset.select_related("data_source", "publisher")
    serializer_class = KeywordSerializer
    permission_classes = [
        DataSourceResourceEditPermission & OrganizationUserEditPermission
    ]

    @extend_schema(
        summary="Update a keyword",
        description=(
            "Keyword can be updated if the user has appropriate access permissions. The original "
            "implementation behaves like PATCH, ie. if some field is left out from the PUT call, "
            "its value is retained in database. In order to ensure consistent behaviour, users "
            "should always supply every field in PUT call."
        ),
        responses={
            200: OpenApiResponse(
                KeywordSerializer,
                description="Keyword has been successfully partially updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Keyword was not found.",
            ),
        },
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Partially update a keyword",
        responses={
            200: OpenApiResponse(
                KeywordSerializer,
                description="Keyword has been successfully partially updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Keyword was not found.",
            ),
        },
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete a keyword",
        description="Keyword can be deleted if the user has appropriate access permissions.",
        responses={
            204: OpenApiResponse(
                description="Keyword has been successfully deleted.",
            ),
            **get_common_api_error_responses(excluded_codes=[400]),
            404: OpenApiResponse(
                description="Keyword was not found.",
            ),
        },
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.deprecate()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Retrieve information about a single keyword",
        auth=[],
        responses={
            200: OpenApiResponse(
                KeywordSerializer,
                description="Keyword record.",
            ),
            **get_common_api_error_responses(excluded_codes=[400, 401]),
            404: OpenApiResponse(
                description="Keyword was not found.",
            ),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        try:
            keyword = Keyword.objects.get(pk=kwargs["pk"])
        except Keyword.DoesNotExist:
            raise Http404()
        if replacement_keyword := keyword.get_replacement():
            return HttpResponsePermanentRedirect(
                reverse(
                    "keyword-detail",
                    kwargs={"pk": replacement_keyword.pk},
                    request=request,
                )
            )
        if keyword.deprecated:
            raise KeywordDeprecatedException()

        return super().retrieve(request, *args, **kwargs)


class KeywordDeprecatedException(APIException):
    status_code = 410
    default_detail = "Keyword has been deprecated."
    default_code = "gone"


class KeywordListViewSet(
    UserDataSourceAndOrganizationMixin,
    JSONAPIViewMixin,
    AuditLogApiViewMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    # publisher relation performs better with prefetch than selected,
    # while data_source has less queries with select
    queryset = (
        Keyword.objects.all()
        .select_related("data_source")
        .prefetch_related("publisher", "alt_labels")
    )
    serializer_class = KeywordSerializer
    filter_backends = (filters.OrderingFilter,)
    ordering_fields = ("n_events", "id", "name", "data_source")
    ordering = ("-data_source", "-n_events", "name")
    permission_classes = [
        DataSourceResourceEditPermission & OrganizationUserEditPermission
    ]

    @extend_schema(summary="Create a new keyword")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Return a list of keywords used for describing events",
        description=render_to_string("swagger/keyword_list_description.html"),
        auth=[],
        parameters=[
            OpenApiParameter(
                name="data_source",
                type=OpenApiTypes.STR,
                description=(
                    "Search for keywords (<b>note</b>: NOT events) that come from the specified "
                    "data source (see data source in keyword definition)."
                ),
            ),
            IncludeOpenApiParameter(),
            OpenApiParameter(
                name="text",
                type=OpenApiTypes.STR,
                description=(
                    "Search for keywords (<b>note</b>: NOT events) that contain the given string. "
                    "This applies even when <code>show_all_keywords</code> is specified. "
                    "Alternative name for the parameter is <code>filter</code>."
                ),
            ),
            OpenApiParameter(
                name="free_text",
                type=OpenApiTypes.STR,
                description=(
                    "While the <code>text</code> search is looking for the keywords containg "
                    "exact matches of the search string, <code>free_text</code> retrieves keywords "
                    "on the basis of similarity. Results are sorted by similarity."
                ),
            ),
            OpenApiParameter(
                name="has_upcoming_events",
                type=OpenApiTypes.BOOL,
                description=(
                    "To show only the keywords which are used in the upcoming events supply the "
                    "<code>has_upcoming_events</code> query parameter."
                ),
            ),
            OpenApiParameter(
                name="show_all_keywords",
                type=OpenApiTypes.BOOL,
                description=(
                    "Show all keywords, including those that are not associated with any events. "
                    "Otherwise such keywords are hidden. When <code>show_all_keywords</code> is "
                    "specified, no other filter is applied, <b>except</b> <code>filter</code> and "
                    "<code>text</code> (match for keywords beginning with string)."
                ),
            ),
            OpenApiParameter(
                name="show_deprecated",
                type=OpenApiTypes.BOOL,
                description=(
                    "Show all keywords, including those that are deprecated. By default such "
                    "keywords are hidden. When <code>show_all_keywords</code> is specified, no "
                    "other filter is applied, <b>except</b> <code>filter</code> and "
                    "<code>text</code> (match for keywords beginning with string)."
                ),
            ),
            OpenApiParameter(
                name="sort",
                type=OpenApiTypes.STR,
                description=(
                    "Sort the returned keywords in the given order. Possible sorting criteria are "
                    "<code>n_events</code>, <code>id</code>, <code>name</code> and "
                    "<code>data_source</code>. The default ordering is <code>-data_source</code>, "
                    "<code>-n_events</code>, <code>name</code>."
                ),
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        """
        Return Keyword queryset.

        If the request has no filter parameters, we only return keywords that meet the following criteria:
        -the keyword has events
        -the keyword is not deprecated

        Supported keyword filtering parameters:
        data_source (only keywords with the given data sources are included)
        filter (only keywords containing the specified string are included)
        show_all_keywords (keywords without events are included)
        show_deprecated (deprecated keywords are included)
        """

        queryset = self.queryset
        data_source = self.request.query_params.get("data_source")
        # Filter by data source, multiple sources separated by comma
        if data_source:
            data_source = data_source.lower().split(",")
            queryset = queryset.filter(data_source__in=data_source)
        if self.request.query_params.get("has_upcoming_events") and parse_bool(
            self.request.query_params.get("has_upcoming_events"), "has_upcoming_events"
        ):
            queryset = queryset.filter(has_upcoming_events=True)
        else:
            if not self.request.query_params.get("show_all_keywords"):
                queryset = queryset.filter(n_events__gt=0)
            if not self.request.query_params.get("show_deprecated"):
                queryset = queryset.filter(deprecated=False)

        if self.request.query_params.get("free_text"):
            val = self.request.query_params.get("free_text")
            # no need to search English if there are accented letters
            langs = (
                ["fi", "sv"]
                if re.search("[\u00C0-\u00FF]", val)
                else ["fi", "sv", "en"]
            )
            tri = [TrigramSimilarity(f"name_{i}", val) for i in langs]
            queryset = queryset.annotate(simile=Greatest(*tri)).filter(simile__gt=0.2)
            self.ordering_fields = ("simile", *self.ordering_fields)
            self.ordering = ("-simile", *self.ordering)

        # Optionally filter keywords by filter parameter,
        # can be used e.g. with typeahead.js
        val = self.request.query_params.get("text") or self.request.query_params.get(
            "filter"
        )
        if val:
            # Also consider alternative labels to broaden the search!
            qset = _text_qset_by_translated_field("name", val) | Q(
                alt_labels__name__icontains=val
            )
            queryset = queryset.filter(qset).distinct()
        return queryset


register_view(KeywordViewSet, "keyword")
register_view(KeywordListViewSet, "keyword", base_name="keywords")


class KeywordSetViewSet(
    UserDataSourceAndOrganizationMixin,
    JSONAPIViewMixin,
    AuditLogApiViewMixin,
    viewsets.ModelViewSet,
):
    queryset = KeywordSet.objects.all().select_related("data_source")
    serializer_class = KeywordSetSerializer
    permission_classes = [
        DataSourceResourceEditPermission & OrganizationUserEditPermission
    ]
    permit_regular_user_edit = True

    @extend_schema(
        summary="Create a new keyword set",
        responses={
            201: OpenApiResponse(
                KeywordSetSerializer,
                description="Keyword set has been successfully created.",
            ),
            **get_common_api_error_responses(),
        },
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Update a keyword set",
        description=(
            "Keyword set can be updated if the user has appropriate access permissions. The "
            "original implementation behaves like PATCH, ie. if some field is left out from the "
            "PUT call, its value is retained in database. In order to ensure consistent "
            "behaviour, users should always supply every field in PUT call."
        ),
        responses={
            200: OpenApiResponse(
                KeywordSetSerializer,
                description="Keyword set has been successfully updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Keyword set was not found.",
            ),
        },
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Partially update a keyword set",
        responses={
            200: OpenApiResponse(
                KeywordSetSerializer,
                description="Keyword set has been successfully partially updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Keyword set was not found.",
            ),
        },
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete a keyword set",
        description="Keyword set can be deleted if the user has appropriate access permissions.",
        responses={
            204: OpenApiResponse(
                description="Keyword set has been successfully deleted.",
            ),
            404: OpenApiResponse(
                description="Keyword set was not found.",
            ),
        },
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Return a list of keyword sets for grouping keywords",
        description=render_to_string("swagger/keyword_set_list_description.html"),
        auth=[],
        parameters=[
            IncludeOpenApiParameter(),
            OpenApiParameter(
                name="text",
                type=OpenApiTypes.STR,
                description=(
                    "Search for keyword sets that contain the given string in name or id fields."
                ),
            ),
            OpenApiParameter(
                name="sort",
                type=OpenApiTypes.STR,
                description=(
                    "Sort the returned keyword sets in the given order. Possible sorting criteria "
                    "are <code>name</code>, <code>usage</code> and <code>data_source.</code>"
                ),
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Return information about single keyword set",
        auth=[],
        responses={
            200: OpenApiResponse(
                KeywordSetSerializer,
                description="Keyword set record.",
            ),
            **get_common_api_error_responses(excluded_codes=[400, 401]),
            404: OpenApiResponse(
                description="Keyword set was not found.",
            ),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def filter_queryset(self, queryset):
        # orderd by name, id, usage
        # search by name
        qexpression = None
        val = self.request.query_params.get("text", None)
        if val:
            qlist = [
                Q(name__icontains=i)
                | Q(name_fi__icontains=i)
                | Q(name_en__icontains=i)
                | Q(name_sv__icontains=i)
                | Q(id__icontains=i)
                for i in val.split(",")
            ]
            qexpression = reduce(or_, qlist)
        if qexpression:
            qset = KeywordSet.objects.filter(qexpression)
        else:
            qset = KeywordSet.objects.all()

        val = self.request.query_params.get("sort", None)
        if val:
            allowed_fields = {"name", "id", "usage", "-name", "-id", "-usage"}
            vals = val.split(",")
            unallowed_params = set(vals) - allowed_fields
            if unallowed_params:
                raise ParseError(
                    f"It is possible to sort with the following params only: {allowed_fields}"
                )
            qset = qset.order_by(*vals)
        return qset


register_view(KeywordSetViewSet, "keyword_set")


class PlaceRetrieveViewSet(
    UserDataSourceAndOrganizationMixin,
    JSONAPIViewMixin,
    GeoModelAPIView,
    AuditLogApiViewMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Place.objects.all()
    queryset = queryset.select_related("data_source", "publisher")
    serializer_class = PlaceSerializer
    permission_classes = [
        DataSourceResourceEditPermission & OrganizationUserEditPermission
    ]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.setdefault("skip_fields", set()).add("origin_id")
        return context

    @extend_schema(
        summary="Update a place",
        description=(
            "Place can be updated if the user has appropriate access permissions. The original "
            "implementation behaves like PATCH, ie. if some field is left out from the PUT call, "
            "its value is retained in database. In order to ensure consistent behaviour, users "
            "should always supply every field in PUT call."
        ),
        responses={
            200: OpenApiResponse(
                PlaceSerializer,
                description="Place has been successfully updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Place was not found.",
            ),
        },
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Partially update a place",
        responses={
            200: OpenApiResponse(
                PlaceSerializer,
                description="Place has been successfully partially updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Place was not found.",
            ),
        },
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete a place",
        description="Place can be deleted if the user has appropriate access permissions.",
        responses={
            404: OpenApiResponse(
                description="Place was not found.",
            ),
        },
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Return information for a single place",
        auth=[],
        responses={
            200: OpenApiResponse(
                PlaceSerializer,
                description="Place record.",
            ),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        try:
            place = Place.objects.get(pk=kwargs["pk"])
        except Place.DoesNotExist:
            raise Http404()
        if place.deleted:
            if place.replaced_by:
                place = place.get_replacement()
                return HttpResponsePermanentRedirect(
                    reverse("place-detail", kwargs={"pk": place.pk}, request=request)
                )
            else:
                raise PlaceDeletedException()
        return super().retrieve(request, *args, **kwargs)


class PlaceDeletedException(APIException):
    status_code = 410
    default_detail = "Place has been deleted."
    default_code = "gone"


class PlaceListViewSet(
    UserDataSourceAndOrganizationMixin,
    GeoModelAPIView,
    JSONAPIViewMixin,
    AuditLogApiViewMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Place.objects.none()
    serializer_class = PlaceSerializer
    filter_backends = (
        django_filters.rest_framework.DjangoFilterBackend,
        filters.OrderingFilter,
    )
    filterset_class = PlaceFilter
    ordering_fields = (
        "n_events",
        "id",
        "name",
        "data_source",
        "street_address",
        "postal_code",
    )
    ordering = (
        "-n_events",
        "-data_source",
        "name",
    )  # we want to display tprek before osoite etc.
    permission_classes = [
        DataSourceResourceEditPermission & OrganizationUserEditPermission
    ]

    @extend_schema(
        summary="Return a list of places used for describing events",
        description=render_to_string("swagger/place_list_description.html"),
        auth=[],
        parameters=[
            OpenApiParameter(
                name="data_source",
                type=OpenApiTypes.STR,
                description=(
                    "Search for places that come from the specified source system."
                ),
            ),
            OpenApiParameter(
                name="text",
                type=OpenApiTypes.STR,
                description=(
                    "Search for places that contain the given string. This applies even when "
                    "show_all_places is specified. Alternative name for the parameter is "
                    "<code>filter</code>."
                ),
            ),
            OpenApiParameter(
                name="has_upcoming_events",
                type=OpenApiTypes.BOOL,
                description=(
                    "To show only the places which are used in the upcoming events supply the "
                    "<code>has_upcoming_events</code> query parameter."
                ),
            ),
            OpenApiParameter(
                name="show_all_places",
                type=OpenApiTypes.BOOL,
                description=(
                    "Show all places, including those that are not hosting any events. "
                    "Otherwise such places are hidden. When show_all_places is specified, "
                    "no other filter is applied."
                ),
            ),
            OpenApiParameter(
                name="show_deleted",
                type=OpenApiTypes.BOOL,
                description=(
                    "Show all keywords, including those that are deleted. "
                    "By default such keywords are hidden."
                ),
            ),
            OpenApiParameter(
                name="sort",
                type=OpenApiTypes.STR,
                description=(
                    "Sort the returned places in the given order. Possible sorting criteria are "
                    "<code>n_events</code>, <code>id</code>, <code>name</code>, "
                    "<code>street_address</code> and <code>postal_code</code>. "
                    "The default ordering is <code>-n_events</code>."
                ),
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Create a new place",
        responses={
            201: OpenApiResponse(
                PlaceSerializer,
                description="Place has been successfully created.",
            ),
            **get_common_api_error_responses(),
        },
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        """
        Return Place queryset.

        If the request has no filter parameters, we only return places that meet the following criteria:
        -the place has events
        -the place is not deleted

        Supported places filtering parameters:
        data_source (only places with the given data sources are included)
        filter (only places containing the specified string are included)
        show_all_places (places without events are included)
        show_deleted (deleted places are included)
        """
        queryset = Place.objects.select_related(
            "data_source",  # Select related to support ordering
        ).prefetch_related(
            "publisher",  # Performs much better as a prefetch
            Prefetch(
                "divisions",
                AdministrativeDivision.objects.all()
                .select_related("type", "municipality")
                .prefetch_related("municipality__translations", "translations"),
            ),
            # Fields below are mostly null -> prefetch faster than select
            "created_by",
            "last_modified_by",
            "image",
            "parent",
            "replaced_by",
        )
        data_source = self.request.query_params.get("data_source")
        # Filter by data source, multiple sources separated by comma
        if data_source:
            data_source = data_source.lower().split(",")
            queryset = queryset.filter(data_source__in=data_source)
        if self.request.query_params.get("has_upcoming_events") and parse_bool(
            self.request.query_params.get("has_upcoming_events"), "has_upcoming_events"
        ):
            queryset = queryset.filter(has_upcoming_events=True)
        else:
            if not self.request.query_params.get("show_all_places"):
                queryset = queryset.filter(n_events__gt=0)
            if not self.request.query_params.get("show_deleted"):
                queryset = queryset.filter(deleted=False)

        # Optionally filter places by filter parameter,
        # can be used e.g. with typeahead.js
        # match to street as well as name, to make it easier to find units by address
        val = self.request.query_params.get("text") or self.request.query_params.get(
            "filter"
        )
        if val:
            qset = _text_qset_by_translated_field(
                "name", val
            ) | _text_qset_by_translated_field("street_address", val)
            queryset = queryset.filter(qset)
        return queryset


register_view(PlaceRetrieveViewSet, "place")
register_view(PlaceListViewSet, "place", base_name="places")


class LanguageViewSet(
    JSONAPIViewMixin, AuditLogApiViewMixin, viewsets.ReadOnlyModelViewSet
):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    filterset_fields = ("service_language",)

    @extend_schema(
        summary="Return a list of languages used for describing events and registrations",
        description=render_to_string("swagger/language_list_description.html"),
        auth=[],
        parameters=[
            OpenApiParameter(
                name="service_language",
                type=OpenApiTypes.BOOL,
                description=(
                    "Show only service languages or languages that are not service languages."
                ),
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Return information for a single language",
        description="Can be used to retrieve translations for a single language.",
        auth=[],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


register_view(LanguageViewSet, "language")


class OrganizationViewSet(
    UserDataSourceAndOrganizationMixin,
    JSONAPIViewMixin,
    AuditLogApiViewMixin,
    viewsets.ModelViewSet,
):
    queryset = Organization.objects.all()
    permission_classes = [DataSourceResourceEditPermission & OrganizationEditPermission]
    filterset_class = OrganizationFilter

    @extend_schema(
        summary="Return a list of organizations that publish events",
        description=render_to_string("swagger/organization_list_description.html"),
        auth=[],
        parameters=[
            # Rest of the parameters are described in the filter class.
            OpenApiParameter(
                name="child",
                type=OpenApiTypes.STR,
                description=(
                    "Get the parent organization and all its ancestors for the given "
                    "organization id."
                ),
            ),
            OpenApiParameter(
                name="parent",
                type=OpenApiTypes.STR,
                description=(
                    "Get all suborganizations and their descendants for the given organization id."
                ),
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Create a new organization",
        responses={
            201: OpenApiResponse(
                OrganizationDetailSerializer,
                description="Organization has been successfully created.",
            ),
            **get_common_api_error_responses(),
        },
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Update an organization",
        description=(
            "Organization can be updated if the user has appropriate access permissions. "
            "The original implementation behaves like PATCH, ie. if some field is left out from "
            "the PUT call, its value is retained in database. In order to ensure consistent "
            "behaviour, users should always supply every field in PUT call."
        ),
        responses={
            200: OpenApiResponse(
                OrganizationDetailSerializer,
                description="Organization has been successfully updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Organization was not found.",
            ),
        },
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Partially update an organization",
        responses={
            200: OpenApiResponse(
                OrganizationDetailSerializer,
                description="Organization has been successfully partially updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Organization was not found.",
            ),
        },
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete an organization",
        description="Organization can be deleted if the user has appropriate access permissions.",
        responses={
            204: OpenApiResponse(
                description="Organization has been successfully deleted.",
            ),
            **get_common_api_error_responses(excluded_codes=[400]),
            404: OpenApiResponse(
                description="Organization was not found.",
            ),
        },
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Return information for a single organization",
        auth=[],
        responses={
            200: OpenApiResponse(
                OrganizationDetailSerializer,
                description="Organization record.",
            ),
            **get_common_api_error_responses(excluded_codes=[400, 401]),
            404: OpenApiResponse(
                description="Organization was not found.",
            ),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_serializer_class(self, *args, **kwargs):
        if self.action in ["create", "retrieve", "update", "partial_update"]:
            return OrganizationDetailSerializer
        else:
            return OrganizationListSerializer

    def get_queryset(self):
        queryset = Organization.objects.prefetch_related(
            "regular_users",
            "financial_admin_users",
            "registration_admin_users",
            "admin_users",
        ).prefetch_related(
            Prefetch(
                "children",
                queryset=Organization.objects.filter(
                    internal_type="normal"
                ),  # noqa E501
                to_attr="sub_organizations",
            ),
            Prefetch(
                "children",
                queryset=Organization.objects.filter(
                    internal_type="affiliated"
                ),  # noqa E501
                to_attr="affiliated_organizations",
            ),
        )
        child_id = self.request.query_params.get("child", None)
        if child_id:
            try:
                queryset = queryset.get(id=child_id).get_ancestors()
            except Organization.DoesNotExist:
                queryset = queryset.none()

        parent_id = self.request.query_params.get("parent", None)
        if parent_id:
            try:
                queryset = queryset.get(id=parent_id).get_descendants()
            except Organization.DoesNotExist:
                queryset = queryset.none()
        return queryset

    @staticmethod
    def _get_web_store_objects(organization, relation_name):
        for ancestor in organization.get_ancestors(ascending=True, include_self=True):
            if objects := list(getattr(ancestor, relation_name).filter(active=True)):
                return objects

        return []

    @extend_schema(
        exclude=settings.WEB_STORE_INTEGRATION_ENABLED is False,
        operation_id="organization_merchants_list",
        summary="Return a list of merchants for an organization",
        description=(
            "Returns a list of merchants for an organization. If the organization itself does not "
            "have merchants, they will be returned from the closest ancestor that has them. "
            "Only admin users are allowed to use this endpoint."
        ),
        responses={
            200: OpenApiResponse(
                WebStoreMerchantSerializer(many=True),
            ),
            **get_common_api_error_responses(excluded_codes=[400]),
            404: OpenApiResponse(
                description="Web store integration is not enabled.",
            ),
        },
    )
    @action(
        methods=["get"],
        detail=True,
        permission_classes=[OrganizationWebStoreMerchantsAndAccountsPermission],
    )
    def merchants(self, request, pk=None, version=None):
        if not settings.WEB_STORE_INTEGRATION_ENABLED:
            return Response(status=status.HTTP_404_NOT_FOUND)

        organization = self.get_object(skip_log_ids=True)
        merchants = self._get_web_store_objects(organization, "web_store_merchants")
        self._add_audit_logged_object_ids(merchants)

        return Response(
            data=WebStoreMerchantSerializer(
                merchants,
                many=True,
                context=self.get_serializer_context(),
                organization=organization,
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        exclude=settings.WEB_STORE_INTEGRATION_ENABLED is False,
        operation_id="organization_accounts_list",
        summary="Return a list of accounts for an organization",
        description=(
            "Returns a list of accounts for an organization. If the organization itself does not "
            "have accounts, they will be returned from the closest ancestor that has them. "
            "Only admin users are allowed to use this endpoint."
        ),
        responses={
            200: OpenApiResponse(
                WebStoreAccountSerializer(many=True),
            ),
            **get_common_api_error_responses(excluded_codes=[400]),
            404: OpenApiResponse(
                description="Web store integration is not enabled.",
            ),
        },
    )
    @action(
        methods=["get"],
        detail=True,
        permission_classes=[OrganizationWebStoreMerchantsAndAccountsPermission],
    )
    def accounts(self, request, pk=None, version=None):
        if not settings.WEB_STORE_INTEGRATION_ENABLED:
            return Response(status=status.HTTP_404_NOT_FOUND)

        organization = self.get_object(skip_log_ids=True)
        accounts = self._get_web_store_objects(organization, "web_store_accounts")
        self._add_audit_logged_object_ids(accounts)

        return Response(
            data=WebStoreAccountSerializer(
                accounts,
                many=True,
            ).data,
            status=status.HTTP_200_OK,
        )


register_view(OrganizationViewSet, "organization")


class DataSourceViewSet(
    JSONAPIViewMixin, AuditLogApiViewMixin, viewsets.ReadOnlyModelViewSet
):
    queryset = DataSource.objects.all()
    serializer_class = DataSourceSerializer
    permission_classes = [GuestRetrieve | UserIsAdminInAnyOrganization]

    @extend_schema(
        summary="Return a list of data sources",
        description=(
            "The returned list describes data sources. Only admin users are allowed to use "
            "this endpoint."
        ),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Return information for a single data source",
        description=(
            "Can be used to retrieve a single data source. Only admin users are allowed to "
            "use this endpoint."
        ),
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


register_view(DataSourceViewSet, "data_source")


class OrganizationClassViewSet(
    JSONAPIViewMixin,
    AuditLogApiViewMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = OrganizationClass.objects.all()
    serializer_class = OrganizationClassSerializer
    permission_classes = [GuestRetrieve | UserIsAdminInAnyOrganization]

    @extend_schema(
        summary="Return a list of organization classes",
        description=(
            "The returned list describes organization classes used for organization "
            "classification. Only admin users are allowed to use this endpoint."
        ),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Return information for a single organization class",
        description=(
            "Can be used to retrieve a single organization class. Only admin users are allowed "
            "to use this endpoint"
        ),
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


register_view(OrganizationClassViewSet, "organization_class")


class ImageViewSet(
    UserDataSourceAndOrganizationMixin,
    JSONAPIViewMixin,
    AuditLogApiViewMixin,
    viewsets.ModelViewSet,
):
    queryset = Image.objects.all().select_related(
        "data_source",
        "publisher",
        "data_source",
        "created_by",
        "last_modified_by",
        "license",
    )
    serializer_class = ImageSerializer
    pagination_class = LargeResultsSetPagination
    filter_backends = (filters.OrderingFilter,)
    ordering_fields = ("last_modified_time", "id", "name")
    ordering = ("-last_modified_time",)
    permission_classes = [DataSourceResourceEditPermission & IsObjectEditableByUser]

    @extend_schema(
        summary="Return a list of images",
        description=render_to_string("swagger/image_list_description.html"),
        auth=[],
        parameters=[
            IncludeOpenApiParameter(),
            OpenApiParameter(
                name="text",
                type=OpenApiTypes.STR,
                description="Search images that contain a specific string.",
            ),
            OpenApiParameter(
                name="publisher",
                type=OpenApiTypes.STR,
                description=(
                    "Search for images published by the given organization as specified by id. "
                    "Multiple ids are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="data_source",
                type=OpenApiTypes.STR,
                description=(
                    "Search for images that come from the specified source system. "
                    "Multiple data sources are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="created_by",
                type=OpenApiTypes.BOOL,
                description="Search for images created by the authenticated user.",
            ),
            OpenApiParameter(
                name="sort",
                type=OpenApiTypes.STR,
                description=(
                    "Default ordering is descending order by <code>-last_modified_time</code>. "
                    "You may also order results by <code>id</code> and <code>name</code>."
                ),
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Create a new image",
        description=(
            "There are two ways to create an image object. The image file can be posted as a "
            "multipart request, but the endpoint also accepts a simple JSON object with an "
            "external url in the url field. This allows using external images for events without "
            "saving them on the API server."
        ),
        request={
            "multipart/form-data": OpenApiRequest(
                request=inline_serializer(
                    "ImageCreateSerializer",
                    fields={
                        "image": serializers.ImageField(),
                    },
                ),
            ),
        },
        responses={
            201: OpenApiResponse(
                ImageSerializer,
                description="Image has been successfully created.",
            ),
            **get_common_api_error_responses(),
        },
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Update an image",
        description=(
            "Image can be updated if the user has appropriate access permissions. The original "
            "implementation behaves like PATCH, ie. if some field is left out from the PUT call, "
            "its value is retained in database. In order to ensure consistent behaviour, users "
            "should always supply every field in PUT call."
        ),
        responses={
            200: OpenApiResponse(
                ImageSerializer,
                description="Image has been successfully updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Image was not found.",
            ),
        },
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Partially update an image",
        responses={
            200: OpenApiResponse(
                ImageSerializer,
                description="Image has been successfully partially updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Image was not found.",
            ),
        },
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete an image",
        description="Image can be deleted if the user has appropriate access permissions.",
        responses={
            204: OpenApiResponse(
                description="Image has been successfully deleted.",
            ),
            **get_common_api_error_responses(excluded_codes=[400]),
            404: OpenApiResponse(
                description="Image was not found.",
            ),
        },
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Return information for a single image",
        auth=[],
        responses={
            200: OpenApiResponse(
                ImageSerializer,
                description="Image record.",
            ),
            **get_common_api_error_responses(excluded_codes=[400, 401]),
            404: OpenApiResponse(
                description="Image was not found.",
            ),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        publisher = self.request.query_params.get("publisher", None)
        if publisher:
            publisher = publisher.lower().split(",")
            q = get_publisher_query(publisher)
            queryset = queryset.filter(q)

        data_source = self.request.query_params.get("data_source")
        # Filter by data source, multiple sources separated by comma
        if data_source:
            data_source = data_source.lower().split(",")
            queryset = queryset.filter(data_source__in=data_source)

        created_by = self.request.query_params.get("created_by")
        if created_by:
            if self.request.user.is_authenticated:
                # only displays events by the particular user
                queryset = queryset.filter(created_by=self.request.user)
            else:
                queryset = queryset.none()
        val = self.request.query_params.get("text")
        if val:
            val = val.lower()
            filter_query = Q(name__icontains=val) | Q(alt_text__icontains=val)

            queryset = queryset.filter(filter_query)
        return queryset

    def perform_destroy(self, instance):
        user = self.request.user

        # User has to be admin or superuser to delete the image
        if not instance.can_be_deleted_by(user):
            raise PermissionDenied()
        if isinstance(user, ApiKeyUser):
            # allow updating only if the api key matches instance data source
            if instance.data_source != user.data_source:
                raise PermissionDenied()
        else:
            # without api key, data_source should have user_editable_resources set to True
            if not instance.is_user_editable_resources():
                raise PermissionDenied()

        super().perform_destroy(instance)


register_view(ImageViewSet, "image", base_name="image")


def parse_duration_string(duration):
    """
    Parse duration string expressed in format
    86400 or 86400s (24 hours)
    180m or 3h (3 hours)
    3d (3 days)
    """
    m = re.match(r"(\d+)\s*(d|h|m|s)?$", duration.strip().lower())
    if not m:
        raise ParseError("Invalid duration supplied. Try '1d', '2h' or '180m'.")
    val, unit = m.groups()
    if not unit:
        unit = "s"

    if unit == "s":
        mul = 1
    elif unit == "m":
        mul = 60
    elif unit == "h":
        mul = 3600
    elif unit == "d":
        mul = 24 * 3600

    return int(val) * mul


def _terms_to_regex(terms, operator: Literal["AND", "OR"]):
    """
    Create a compiled regex from of the provided terms of the form
    r'(\b(term1){e<2}')|(\b(term2){e<2})" This would match a string
    with terms aligned in any order allowing two edits per term.
    """
    if operator == "AND":
        regex_join = ""
    elif operator == "OR":
        regex_join = "|"
    else:
        raise ValueError("Invalid operator")

    vals = terms.split(",")
    valexprs = []
    for val in vals:
        if len(val) < 8:
            e = 1
        else:
            e = 2
        escaped_val = regex.escape(val)
        expr = r"(\b" + f"({escaped_val}){{e<{e}}})"
        valexprs.append(expr)
    expr = f"{regex_join.join(valexprs)}"
    return regex.compile(expr, regex.IGNORECASE)


def _get_queryset_from_cache(params, param, cache_name, operator, queryset):
    val = params.get(param, None)
    if not val:
        return queryset

    cache_values = cache.get(cache_name)
    if not cache_values:
        logger.error(f"Missed cache {cache_name}")
        return queryset

    rc = _terms_to_regex(val, operator)
    ids = {k for k, v in cache_values.items() if rc.search(v, concurrent=True)}
    queryset = queryset.filter(id__in=ids)

    return queryset


def _get_queryset_from_cache_many(params, param, cache_name, operator, queryset):
    val = params.get(param, None)
    if not val:
        return queryset

    cache_values = cache.get_many(cache_name)
    if not cache_values:
        logger.error(f"Missed cache {cache_name}")
        return queryset

    rc = _terms_to_regex(val, operator)
    cached_ids = {k: v for i in cache_values.values() for k, v in i.items()}

    ids = {k for k, v in cached_ids.items() if rc.search(v, concurrent=True)}

    queryset = queryset.filter(id__in=ids)

    return queryset


def _find_keyword_replacements(keyword_ids: list[str]) -> tuple[list[Keyword], bool]:
    """
    Convert a list of keyword ids into keyword objects with
    replacements applied.

    :return: a pair containing a list of keywords and a boolean indicating
             whether all keywords were found
    """
    keywords = Keyword.objects.filter(id__in=keyword_ids).select_related("replaced_by")
    found_all_keywords = len(keyword_ids) == len(keywords)
    replaced_keywords = [keyword.get_replacement() or keyword for keyword in keywords]
    return list(set(replaced_keywords)), found_all_keywords


def _filter_events_keyword_or(queryset: QuerySet, keyword_ids: list[str]) -> QuerySet:
    """
    Given an Event queryset, apply OR filter on keyword ids
    """
    keywords, __ = _find_keyword_replacements(keyword_ids)
    keyword_ids = [keyword.pk for keyword in keywords]

    kw_qs = Event.keywords.through.objects.filter(
        event=OuterRef("pk"), keyword__in=keyword_ids
    )
    audience_qs = Event.audience.through.objects.filter(
        event=OuterRef("pk"), keyword__in=keyword_ids
    )
    return queryset.filter(Exists(kw_qs) | Exists(audience_qs))


def _filter_event_queryset(queryset, params, srs=None):  # noqa: C901
    """
    Filter events queryset by params
    (e.g. self.request.query_params ingit EventViewSet)
    """
    # Please keep in mind that .distinct() will absolutely kill
    # performance of event queries. To avoid duplicate rows in filters
    # consider using Exists instead.
    # Filtering against the through table can also provide
    # benefits (see _filter_events_keyword_or)

    val = params.get("registration", None)
    if val and parse_bool(val, "registration"):
        queryset = queryset.exclude(registration=None)
    elif val:
        queryset = queryset.filter(registration=None)

    val = params.get("enrolment_open", None)
    if val:
        queryset = (
            queryset.filter(registration__enrolment_end_time__gte=localtime())
            .annotate(
                free=(
                    F("registration__maximum_attendee_capacity")
                    - Count("registration__signups")
                ),
            )
            .filter(
                Q(free__gte=1) | Q(registration__maximum_attendee_capacity__isnull=True)
            )
        )

    val = params.get("enrolment_open_waitlist", None)
    if val:
        queryset = (
            queryset.filter(registration__enrolment_end_time__gte=localtime())
            .annotate(
                free=(
                    (
                        F("registration__maximum_attendee_capacity")
                        + F("registration__waiting_list_capacity")
                    )
                    - Count("registration__signups")
                ),
            )
            .filter(
                Q(free__gte=1)
                | Q(registration__maximum_attendee_capacity__isnull=True)
                | Q(registration__waiting_list_capacity__isnull=True)
            )
        )

    val = params.get("local_ongoing_text", None)
    if val:
        language = params.get("language", "fi")
        langs = settings.FULLTEXT_SEARCH_LANGUAGES
        if language not in langs.keys():
            raise ParseError(
                f"{language} not supported. Supported options are: {' '.join(langs.values())}"
            )

        val = val.replace(",", " ")
        query = SearchQuery(val, config=langs[language], search_type="plain")
        kwargs = {f"search_vector_{language}": query}
        queryset = (
            queryset.filter(**kwargs)
            .filter(
                end_time__gte=datetime.utcnow().replace(tzinfo=pytz.utc), deleted=False
            )
            .filter(Q(location__id__endswith="internet") | Q(local=True))
        )

    queryset = _get_queryset_from_cache(
        params, "local_ongoing_OR", "local_ids", "OR", queryset
    )
    queryset = _get_queryset_from_cache(
        params, "local_ongoing_AND", "local_ids", "AND", queryset
    )
    queryset = _get_queryset_from_cache(
        params, "internet_ongoing_AND", "internet_ids", "AND", queryset
    )
    queryset = _get_queryset_from_cache(
        params, "internet_ongoing_OR", "internet_ids", "OR", queryset
    )
    queryset = _get_queryset_from_cache(
        params, "local_ongoing_OR", "local_ids", "OR", queryset
    )

    val = params.get("all_ongoing")
    if val and parse_bool(val, "all_ongoing"):
        cache_name = ["internet_ids", "local_ids"]
        cache_values = cache.get_many(cache_name)
        if cache_values:
            ids = {k for i in cache_values.values() for k, v in i.items()}
            queryset = queryset.filter(id__in=ids)
        else:
            logger.error(f"Missed cache {cache_name}")

    queryset = _get_queryset_from_cache_many(
        params, "all_ongoing_AND", ["internet_ids", "local_ids"], "AND", queryset
    )
    queryset = _get_queryset_from_cache_many(
        params, "all_ongoing_OR", ["internet_ids", "local_ids"], "OR", queryset
    )

    vals = params.get("keyword_set_AND", None)
    if vals:
        vals = vals.split(",")
        kw_sets = KeywordSet.objects.filter(id__in=vals).prefetch_related(
            Prefetch("keywords", Keyword.objects.all().only("id"))
        )
        for kw_set in kw_sets:
            kw_ids = [kw.id for kw in kw_set.keywords.all()]
            subqs = Event.objects.filter(
                Q(id=OuterRef("pk"), keywords__in=kw_ids)
                | Q(id=OuterRef("pk"), audience__in=kw_ids)
            )
            queryset = queryset.filter(Exists(subqs))

    vals = params.get("keyword_set_OR", None)
    if vals:
        vals = vals.split(",")
        keyword_sets = KeywordSet.objects.filter(id__in=vals).prefetch_related(
            Prefetch("keywords", Keyword.objects.all().only("id"))
        )
        all_keywords = set()
        for keyword_set in keyword_sets:
            keywords = keyword_set.keywords.all()
            all_keywords.update(keywords)

        kw_qs = Event.keywords.through.objects.filter(
            event=OuterRef("pk"), keyword__in=all_keywords
        )
        audience_qs = Event.audience.through.objects.filter(
            event=OuterRef("pk"), keyword__in=all_keywords
        )
        queryset = queryset.filter(Exists(kw_qs) | Exists(audience_qs))

    if "local_ongoing_OR_set1" in "".join(params):
        count = 1
        all_ids = []
        while f"local_ongoing_OR_set{count}" in params:
            val = params.get(f"local_ongoing_OR_set{count}", None)
            if val:
                rc = _terms_to_regex(val, "OR")
                all_ids.append(
                    {
                        k
                        for k, v in cache.get("local_ids").items()
                        if rc.search(v, concurrent=True)
                    }
                )
            count += 1
        ids = set.intersection(*all_ids) if all_ids else set()
        queryset = queryset.filter(id__in=ids)

    if "internet_ongoing_OR_set1" in "".join(params):
        count = 1
        all_ids = []
        while f"internet_ongoing_OR_set{count}" in params:
            val = params.get(f"internet_ongoing_OR_set{count}", None)
            if val:
                rc = _terms_to_regex(val, "OR")
                all_ids.append(
                    {
                        k
                        for k, v in cache.get("internet_ids").items()
                        if rc.search(v, concurrent=True)
                    }
                )
            count += 1
        ids = set.intersection(*all_ids) if all_ids else set()
        queryset = queryset.filter(id__in=ids)

    if "all_ongoing_OR_set1" in "".join(params):
        count = 1
        all_ids = []
        while f"all_ongoing_OR_set{count}" in params:
            val = params.get(f"all_ongoing_OR_set{count}", None)
            if val:
                rc = _terms_to_regex(val, "OR")
                cached_ids = {
                    k: v
                    for i in cache.get_many(["internet_ids", "local_ids"]).values()
                    for k, v in i.items()
                }  # noqa E501
                all_ids.append(
                    {k for k, v in cached_ids.items() if rc.search(v, concurrent=True)}
                )
            count += 1
        ids = set.intersection(*all_ids) if all_ids else set()
        queryset = queryset.filter(id__in=ids)

    if "keyword_OR_set" in "".join(params):
        rc = regex.compile("keyword_OR_set[0-9]*")
        all_sets = rc.findall("".join(params))
        for i in all_sets:
            val = params.get(i, None)
            if val:
                vals = val.split(",")
                kw_qs = Event.keywords.through.objects.filter(
                    event=OuterRef("pk"), keyword__in=vals
                )
                audience_qs = Event.audience.through.objects.filter(
                    event=OuterRef("pk"), keyword__in=vals
                )
                queryset = queryset.filter(Exists(kw_qs) | Exists(audience_qs))

    val = params.get("internet_based", None)
    if val and parse_bool(val, "internet_based"):
        queryset = queryset.filter(location__id__contains="internet")

    #  Filter by event translated fields and keywords combined. The code is
    #  repeated as this is the first iteration, which will be replaced by a similarity
    #  based search on the index.
    val = params.get("combined_text", None)
    if val:
        val = val.lower()
        vals = val.split(",")

        combined_q = Q()
        for val in vals:
            val_q = Q()
            # Free string search from all translated event fields
            event_fields = EventTranslationOptions.fields
            for field in event_fields:
                # check all languages for each field
                val_q |= _text_qset_by_translated_field(field, val)

            # Free string search from all translated place fields
            place_fields = PlaceTranslationOptions.fields
            for field in place_fields:
                location_field = "location__" + field
                # check all languages for each field
                val_q |= _text_qset_by_translated_field(location_field, val)

            langs = (
                ["fi", "sv"]
                if re.search("[\u00C0-\u00FF]", val)
                else ["fi", "sv", "en"]
            )
            tri = [TrigramSimilarity(f"name_{i}", val) for i in langs]
            keywords = list(
                Keyword.objects.annotate(simile=Greatest(*tri))
                .filter(simile__gt=0.2)
                .order_by("-simile")[:3]
            )

            val_q |= Q(keywords__in=keywords)

            combined_q &= val_q

        # FYI: Biggest slowdown in this filter is the ordering of keywords simile
        queryset = queryset.filter(
            Exists(Event.objects.filter(combined_q, id=OuterRef("pk")).only("id"))
        )

    val = params.get("text", None)
    if val:
        val = val.lower()
        qset = Q()

        # Free string search from all translated event fields
        event_fields = EventTranslationOptions.fields
        for field in event_fields:
            # check all languages for each field
            qset |= _text_qset_by_translated_field(field, val)

        # Free string search from all translated place fields
        place_fields = PlaceTranslationOptions.fields
        for field in place_fields:
            location_field = "location__" + field
            # check all languages for each field
            qset |= _text_qset_by_translated_field(location_field, val)

        queryset = queryset.filter(qset)

    val = params.get("ids", None)
    if val:
        queryset = queryset.filter(id__in=val.strip("/").split(","))

    val = params.get("event_type", None)
    if val:
        vals = val.lower().split(",")
        event_types = {k[1].lower(): k[0] for k in Event.TYPE_IDS}
        search_vals = []
        for v in vals:
            if v not in event_types:
                raise ParseError(
                    _(
                        "Event type can be of the following values: {event_types}"
                    ).format(event_types=" ".join(event_types.keys()))
                )
            search_vals.append(event_types[v])

        queryset = queryset.filter(type_id__in=search_vals)
    else:
        queryset = queryset.filter(type_id=Event.TypeId.GENERAL)

    val = params.get("last_modified_since", None)
    # This should be in format which dateutil.parser recognizes, e.g.
    # 2014-10-29T12:00:00Z == 2014-10-29T12:00:00+0000 (UTC time)
    # or 2014-10-29T12:00:00+0200 (local time)
    if val:
        # This feels like a bug to use end time, but that's how the original
        # implementation since 2014 has worked. No test coverage here at the
        # time of writing, so go figure.
        dt = utils.parse_end_time(val)[0]
        queryset = queryset.filter(Q(last_modified_time__gte=dt))

    start = params.get("start")
    end = params.get("end")
    days = params.get("days")

    if days:
        try:
            days = int(days)
        except ValueError:
            raise ParseError(_("Error while parsing days."))
        if days < 1:
            raise serializers.ValidationError(_("Days must be 1 or more."))

        if start or end:
            raise serializers.ValidationError(
                _("Start or end cannot be used with days.")
            )

        today = datetime.now(datetime_timezone.utc).date()

        start = today.isoformat()
        end = (today + timedelta(days=days)).isoformat()

    if not end:
        # postponed events are considered to be "far" in the future and should be included if end is *not* given
        postponed_q = Q(event_status=Event.Status.POSTPONED)
    else:
        postponed_q = Q()

    if start:
        # Inconsistent behaviour, see test_inconsistent_tz_default
        dt = utils.parse_time(start, default_tz=pytz.timezone(settings.TIME_ZONE))[0]

        # only return events with specified end times, or unspecified start times, during the whole of the event
        # this gets of rid pesky one-day events with no known end time (but known start) after they started
        queryset = queryset.filter(
            Q(end_time__gt=dt, has_end_time=True)
            | Q(end_time__gt=dt, has_start_time=False)
            | Q(start_time__gte=dt)
            | postponed_q
        )

    if end:
        # Inconsistent behaviour, see test_inconsistent_tz_default
        dt = utils.parse_end_time(end, default_tz=pytz.timezone(settings.TIME_ZONE))[0]
        queryset = queryset.filter(Q(end_time__lt=dt) | Q(start_time__lte=dt))

    val = params.get("bbox", None)
    if val:
        bbox_filter = build_bbox_filter(srs, val, "position")
        places = Place.geo_objects.filter(**bbox_filter)
        queryset = queryset.filter(location__in=places)

    # Filter by data source, multiple sources separated by comma
    val = params.get("data_source", None)
    if val:
        val = val.split(",")
        queryset = queryset.filter(data_source_id__in=val)
    else:
        queryset = queryset.exclude(data_source__private=True)

    # Negative filter by data source, multiple sources separated by comma
    val = params.get("data_source!", None)
    if val:
        val = val.split(",")
        queryset = queryset.exclude(data_source_id__in=val)

    # Filter by location id, multiple ids separated by comma
    val = params.get("location", None)
    if val:
        val = val.split(",")
        queryset = queryset.filter(location_id__in=val)

    if val := params.get("keyword", None):
        queryset = _filter_events_keyword_or(queryset, val.split(","))

    # 'keyword_OR' behaves the same way as 'keyword'
    if val := params.get("keyword_OR", None):
        queryset = _filter_events_keyword_or(queryset, val.split(","))

    # Filter by keyword ids requiring all keywords to be present in event
    val = params.get("keyword_AND", None)
    if val:
        keywords, found_all_keywords = _find_keyword_replacements(val.split(","))

        # If some keywords were not found, AND can not match
        if not found_all_keywords:
            return queryset.none()

        q = Q()
        for keyword in keywords:
            q &= Q(keywords__pk=keyword.pk) | Q(audience__pk=keyword.pk)

        for keyword in keywords:
            kw_qs = Event.keywords.through.objects.filter(
                event=OuterRef("pk"), keyword=keyword
            )
            audience_qs = Event.audience.through.objects.filter(
                event=OuterRef("pk"), keyword=keyword
            )
            queryset = queryset.filter(Exists(kw_qs) | Exists(audience_qs))

    # Negative filter for keyword ids
    val = params.get("keyword!", None)
    if val:
        keywords, __ = _find_keyword_replacements(val.split(","))
        keyword_ids = [keyword.pk for keyword in keywords]

        # This yields an AND NOT ((EXISTS.. keywords )) clause in SQL
        # No distinct needed!
        queryset = queryset.exclude(
            Q(keywords__pk__in=keyword_ids) | Q(audience__pk__in=keyword_ids)
        )

    # filter only super or non-super events. to be deprecated?
    val = params.get("recurring", None)
    if val:
        val = val.lower()
        if val == "super":
            # same as ?super_event_type=recurring
            queryset = queryset.filter(super_event_type=Event.SuperEventType.RECURRING)
        elif val == "sub":
            # same as ?super_event_type=none,umbrella, weirdly yielding non-sub events too.
            # don't know if users want this to remain tho. do we want that or is there a need
            # to change this to actually filter only subevents of recurring events?
            queryset = queryset.exclude(super_event_type=Event.SuperEventType.RECURRING)

    val = params.get("max_duration", None)
    if val:
        dur = parse_duration_string(val)
        cond = "end_time - start_time <= %s :: interval"
        queryset = queryset.extra(where=[cond], params=[str(dur)])

    val = params.get("min_duration", None)
    if val:
        dur = parse_duration_string(val)
        cond = "end_time - start_time >= %s :: interval"
        queryset = queryset.extra(where=[cond], params=[str(dur)])

    # Filter by publisher, multiple sources separated by comma
    val = params.get("publisher", None)
    if val:
        val = val.split(",")
        q = get_publisher_query(val)
        queryset = queryset.filter(q)

    # Filter by publisher ancestors, multiple ids separated by comma
    val = params.get("publisher_ancestor", None)
    if val:
        val = val.split(",")
        ancestors = Organization.objects.filter(id__in=val)

        # Get ids of ancestors and all their descendants
        publishers = Organization.objects.none()
        for org in ancestors.all():
            publishers |= org.get_descendants(include_self=True)
        publisher_ids = [org["id"] for org in publishers.all().values("id")]

        q = get_publisher_query(publisher_ids)
        queryset = queryset.filter(q)

    # Filter by publication status
    val = params.get("publication_status", None)
    if val == "draft":
        queryset = queryset.filter(publication_status=PublicationStatus.DRAFT)
    elif val == "public":
        queryset = queryset.filter(publication_status=PublicationStatus.PUBLIC)

    # Filter by event status
    if status_param := params.get("event_status"):
        statuses = []
        for value in (s.lower() for s in status_param.split(",")):
            if value == "eventscheduled":
                statuses.append(Event.Status.SCHEDULED)
            elif value == "eventrescheduled":
                statuses.append(Event.Status.RESCHEDULED)
            elif value == "eventcancelled":
                statuses.append(Event.Status.CANCELLED)
            elif value == "eventpostponed":
                statuses.append(Event.Status.POSTPONED)

        queryset = queryset.filter(event_status__in=statuses)

    # Filter by language, checking both string content and in_language field
    val = params.get("language", None)
    if val:
        val = val.split(",")
        q = Q()
        for lang in val:
            if lang in get_fixed_lang_codes():
                # check string content if language has translations available
                name_arg = {"name_" + lang + "__isnull": False}
                desc_arg = {"description_" + lang + "__isnull": False}
                short_desc_arg = {"short_description_" + lang + "__isnull": False}
                q = (
                    q
                    | Exists(
                        Event.in_language.through.objects.filter(
                            event=OuterRef("pk"), language=lang
                        )
                    )
                    | Q(**name_arg)
                    | Q(**desc_arg)
                    | Q(**short_desc_arg)
                )
            else:
                q = q | Exists(
                    Event.in_language.through.objects.filter(
                        event=OuterRef("pk"), language=lang
                    )
                )

        queryset = queryset.filter(q)

    # Filter by in_language field only
    val = params.get("in_language", None)
    if val:
        val = val.split(",")
        q = Q()
        for lang in val:
            q = q | Exists(
                Event.in_language.through.objects.filter(
                    event=OuterRef("pk"), language=lang
                )
            )

        queryset = queryset.filter(q)

    val = params.get("starts_after", None)
    param = "starts_after"
    if val:
        split_time = val.split(":")
        hour, minute = parse_hours(split_time, param)
        queryset = queryset.filter(start_time__time__gte=datetime_time(hour, minute))

    val = params.get("starts_before", None)
    param = "starts_before"
    if val:
        split_time = val.split(":")
        hour, minute = parse_hours(split_time, param)
        queryset = queryset.filter(start_time__time__lte=datetime_time(hour, minute))

    val = params.get("ends_after", None)
    param = "ends_after"
    if val:
        split_time = val.split(":")
        hour, minute = parse_hours(split_time, param)
        queryset = queryset.filter(end_time__time__gte=datetime_time(hour, minute))

    val = params.get("ends_before", None)
    param = "ends_before"
    if val:
        split_time = val.split(":")
        hour, minute = parse_hours(split_time, param)
        queryset = queryset.filter(end_time__time__lte=datetime_time(hour, minute))

    # Filter by translation only
    val = params.get("translation", None)
    if val:
        val = val.split(",")
        q = Q()
        for lang in val:
            if lang in get_fixed_lang_codes():
                # check string content if language has translations available
                name_arg = {"name_" + lang + "__isnull": False}
                desc_arg = {"description_" + lang + "__isnull": False}
                short_desc_arg = {"short_description_" + lang + "__isnull": False}
                q = q | Q(**name_arg) | Q(**desc_arg) | Q(**short_desc_arg)
            else:
                # language has no translations, matching condition must be false
                q = q | Q(pk__in=[])
        queryset = queryset.filter(q)

    # Filter by audience min age
    val = params.get("audience_min_age", None) or params.get(
        "audience_min_age_lt", None
    )
    if val:
        min_age = parse_digit(val, "audience_min_age")
        queryset = queryset.filter(audience_min_age__lte=min_age)

    val = params.get("audience_min_age_gt", None)
    if val:
        min_age = parse_digit(val, "audience_min_age_gt")
        queryset = queryset.filter(audience_min_age__gte=min_age)

    # Filter by audience max age
    val = params.get("audience_max_age", None) or params.get(
        "audience_max_age_gt", None
    )
    if val:
        max_age = parse_digit(val, "audience_max_age")
        queryset = queryset.filter(audience_max_age__gte=max_age)

    val = params.get("audience_max_age_lt", None)
    if val:
        max_age = parse_digit(val, "audience_max_age_lt")
        queryset = queryset.filter(audience_max_age__lte=max_age)

    # Filter deleted events
    val = params.get("show_deleted", None)
    # ONLY deleted events (for cache updates etc., returns deleted object ids)
    val_deleted = params.get("deleted", None)
    if not val and not val_deleted:
        queryset = queryset.filter(deleted=False)
    if val_deleted:
        queryset = queryset.filter(deleted=True)

    # Filter by free offer
    val = params.get("is_free", None)
    if val and val.lower() in ["true", "false"]:
        # Include events that have at least one free offer
        if val.lower() == "true":
            queryset = queryset.filter(
                Exists(Offer.objects.filter(event=OuterRef("pk"), is_free=True))
            )
        # Include events that have no free offers
        elif val.lower() == "false":
            queryset = queryset.exclude(offers__is_free=True)

    val = params.get("suitable_for", None)
    # Excludes all the events that have max age limit below or min age limit above the age or age range specified.
    # Suitable events with just one age boundary specified are returned, events with no age limits specified are
    # excluded.

    if val:
        vals = val.split(",")
        if len(vals) > 2:
            raise ParseError(
                f"suitable_for takes at maximum two values, you provided {len(vals)}"
            )
        int_vals = [parse_digit(i, "suitable_for") for i in vals]
        if len(int_vals) == 2:
            lower_boundary = min(int_vals)
            upper_boundary = max(int_vals)
        else:
            lower_boundary = upper_boundary = int_vals[0]
        queryset = queryset.exclude(
            Q(audience_min_age__gt=lower_boundary)
            | Q(audience_max_age__lt=upper_boundary)
            | Q(Q(audience_min_age=None) & Q(audience_max_age=None))
        )
    return queryset


class EventExtensionFilterBackend(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        extensions = get_extensions_from_request(request)

        for ext in extensions:
            queryset = ext.filter_event_queryset(request, queryset, view)

        return queryset


class EventDeletedException(APIException):
    status_code = 410
    default_detail = "Event has been deleted."
    default_code = "gone"


class EventViewSet(
    UserDataSourceAndOrganizationMixin,
    JSONAPIViewMixin,
    AuditLogApiViewMixin,
    BulkModelViewSet,
    viewsets.ModelViewSet,
):
    # sub_event prefetches are handled in get_queryset()
    queryset = (
        Event.objects.all()
        .select_related("data_source", "publisher", "created_by", "last_modified_by")
        .prefetch_related(
            "audience",
            "external_links",
            "keywords",
            "images",
            "images__publisher",
            "images__created_by",
            "images__last_modified_by",
            "in_language",
            "offers",
            "registration",
            "videos",
        )
    )

    serializer_class = EventSerializer
    filter_backends = (
        EventOrderingFilter,
        django_filters.rest_framework.DjangoFilterBackend,
        EventExtensionFilterBackend,
    )
    filterset_class = EventFilter
    ordering_fields = (
        "start_time",
        "end_time",
        "duration",
        "last_modified_time",
        "name",
        "maximum_attendee_capacity",
        "minimum_attendee_capacity",
        "enrolment_start_time",
        "enrolment_end_time",
        "registration__enrolment_start_time",
        "registration__enrolment_end_time",
        "enrolment_start",
        "enrolment_end",
    )
    ordering = ("-last_modified_time",)
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [DOCXRenderer]
    permission_classes = [DataSourceResourceEditPermission]
    permit_regular_user_edit = True

    @staticmethod
    def get_serializer_class_for_version(version):
        if version == "v0.1":
            return EventSerializerV0_1
        return EventSerializer

    def get_serializer_class(self):
        return EventViewSet.get_serializer_class_for_version(self.request.version)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.setdefault("skip_fields", set()).update(
            {"headline", "secondary_headline"}
        )
        context["extensions"] = get_extensions_from_request(self.request)

        if self.request.method in ("POST", "PUT", "PATCH"):
            context = {**context, **self.cache_related_fields_to_context(self.request)}

        return context

    @staticmethod
    def _optimize_include(includes, queryset):
        if "location" in includes:
            queryset = queryset.prefetch_related(
                "location__publisher",
                "location__divisions",
                "location__divisions__type",
                "location__divisions__municipality",
                "location__divisions__translations",
            )
        else:
            queryset = queryset.prefetch_related(
                Prefetch("location", Place.objects.all().only("id"))
            )

        if "keywords" in includes:
            queryset = queryset.prefetch_related(
                "audience__alt_labels",
                "audience__publisher",
                "keywords__alt_labels",
                "keywords__publisher",
            )
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in {"list", "retrieve"}:
            context = self.get_serializer_context()
            # prefetch extra if the user want them included
            includes = context.get("include", [])

            queryset = self._optimize_include(includes, queryset)

            if "sub_events" in includes:
                sub_event_qs = self._optimize_include(
                    includes, self.queryset.filter(deleted=False)
                )
                queryset = queryset.prefetch_related(
                    Prefetch("sub_events", sub_event_qs),
                    Prefetch("sub_events__sub_events", sub_event_qs),
                )
            else:
                queryset = queryset.prefetch_related(
                    Prefetch("sub_events", Event.objects.filter(deleted=False))
                )

            return apply_select_and_prefetch(
                queryset=queryset, extensions=get_extensions_from_request(self.request)
            )
        return queryset

    def get_object(self, skip_log_ids=False):
        event = super().get_object()
        if (
            event.publication_status == PublicationStatus.PUBLIC
            or self.request.user.is_authenticated
            and self.request.user.can_edit_event(
                event.publisher,
                event.publication_status,
                event.created_by,
            )
        ):
            if event.deleted:
                raise EventDeletedException()
            return event
        else:
            raise Http404("Event does not exist")

    def filter_queryset(self, queryset):
        """
        TODO: convert to use proper filter framework
        """
        original_queryset = super().filter_queryset(queryset)
        if self.action == "list":
            # we cannot use distinct for performance reasons
            public_queryset = original_queryset.filter(
                publication_status=PublicationStatus.PUBLIC
            )
            editable_queryset = original_queryset.none()
            if self.request.user.is_authenticated:
                editable_queryset = self.request.user.get_editable_events(
                    original_queryset
                )
            # by default, only public events are shown in the event list
            queryset = public_queryset
            # however, certain query parameters allow customizing the listing for authenticated users
            show_all = self.request.query_params.get("show_all")
            if show_all:
                # displays all editable events, including drafts, and public non-editable events
                queryset = editable_queryset | public_queryset

            admin_user = self.request.query_params.get("admin_user")
            registration_admin_user = self.request.query_params.get(
                "registration_admin_user"
            )
            if admin_user and registration_admin_user:
                raise ParseError(
                    "Supply either 'admin_user' or 'registration_admin_user', not both"
                )

            if admin_user:
                # displays all editable events, including drafts, but no other public events
                queryset = editable_queryset

            created_by = self.request.query_params.get("created_by")
            if created_by:
                # only displays events by the particular user
                if self.request.user.is_authenticated:
                    queryset = queryset.filter(created_by=self.request.user)
                else:
                    queryset = queryset.none()
            queryset = _filter_event_queryset(
                queryset, self.request.query_params, srs=self.srs
            )
        elif self.request.method not in permissions.SAFE_METHODS:
            # prevent changing events user does not have write permissions (for bulk operations)
            if isinstance(self.request.data, list):
                try:
                    original_queryset = Event.objects.filter(
                        id__in=[i.get("id", "") for i in self.request.data]
                    )
                except:  # noqa E722
                    raise DRFPermissionDenied("Invalid JSON in request.")

                queryset = self.request.user.get_editable_events(original_queryset)

        return queryset.filter()

    def allow_bulk_destroy(self, qs, filtered):
        return False

    @extend_schema(
        summary="Update an event",
        description=(
            "Events can be updated if the user has appropriate access permissions. The original "
            "implementation behaves like PATCH, ie. if some field is left out from the PUT call, "
            "its value is retained in database. In order to ensure consistent behaviour, users "
            "should always supply every field in PUT call."
        ),
        responses={
            200: OpenApiResponse(
                EventSerializer,
                description="Event has been successfully updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Event was not found.",
            ),
        },
    )
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)

        event_data = serializer.validated_data

        _, org = self.user_data_source_and_organization
        if "publisher" in event_data:
            org = event_data["publisher"]
        if not self.request.user.can_edit_event(
            org, event_data["publication_status"], instance.created_by
        ):
            raise DRFPermissionDenied()

        try:
            serializer.save()
        except WebStoreAPIError as exc:
            raise serializers.ValidationError(exc.messages)

        response = Response(data=serializer.data)

        original_event = Event.objects.get(id=response.data["id"])
        if original_event.replaced_by is not None:
            replacing_event = original_event.replaced_by
            context = self.get_serializer_context()
            response.data = EventSerializer(replacing_event, context=context).data
        return response

    def perform_bulk_update(self, serializer: EventSerializer):
        # Prevent changing an event that user does not have write permissions
        # For bulk update, the editable queryset is filtered in filter_queryset
        # method

        # Prevent changing existing events to a state that user does not have write permissions
        for event_data in serializer.validated_data:
            try:
                instance = serializer.instance.get(id=event_data["id"])
            except Event.DoesNotExist:
                instance = None
            _, org = self.user_data_source_and_organization
            if "publisher" in event_data:
                org = event_data["publisher"]
            if not self.request.user.can_edit_event(
                org,
                event_data["publication_status"],
                instance.created_by if instance else None,
            ):
                raise DRFPermissionDenied()

        try:
            super().perform_update(serializer)
        except WebStoreAPIError as exc:
            raise serializers.ValidationError(exc.messages)

    @extend_schema(
        operation_id="event_bulk_update",
        summary="Bulk update several events",
        description=(
            "Events can be updated if the user has appropriate access permissions. The original "
            "implementation behaves like PATCH, ie. if some field is left out from the PUT call, "
            "its value is retained in database. In order to ensure consistent behaviour, users "
            "should always supply every field in PUT call."
        ),
        request=EventSerializer(many=True),
        responses={
            200: OpenApiResponse(
                EventSerializer(many=True),
                description="Events have been successfully updated.",
            ),
            **get_common_api_error_responses(),
        },
    )
    @transaction.atomic
    def bulk_update(self, request, *args, **kwargs):
        if not isinstance(request.data, list):
            raise DRFPermissionDenied(
                "Invalid JSON in request. Bulk update requires a list"
            )

        serializer = EventSerializer(
            self.filter_queryset(self.get_queryset()),
            data=request.data,
            context=self.get_serializer_context(),
            many=True,
            partial=partial,
        )
        if not serializer.instance:
            raise serializers.ValidationError("Missing matching events to update.")
        serializer.is_valid(raise_exception=True)
        self.perform_bulk_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(exclude=True)
    def partial_bulk_update(self, request, *args, **kwargs):
        return self.bulk_update(request, *args, **kwargs)

    @extend_schema(
        summary="Partially update an event",
        responses={
            200: OpenApiResponse(
                EventSerializer,
                description="Event has been successfully partially updated.",
            ),
            **get_common_api_error_responses(),
            404: OpenApiResponse(
                description="Event was not found.",
            ),
        },
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Create a new event or events",
        request=EventSerializer(many=True),
        responses={
            201: OpenApiResponse(
                EventSerializer,
                description="Event has been successfully created.",
            ),
            **get_common_api_error_responses(),
        },
    )
    @transaction.atomic
    def create(self, *args, **kwargs):
        return super().create(*args, **kwargs)

    @staticmethod
    def _retrieve_ids(key, event, id_data_type: Union[type[str], type[int]] = str):
        if key not in event.keys():
            return []

        if isinstance(event[key], list):
            event_list = event.get(key, [])
        else:
            event_list = [event.get(key, [])]

        id_field = "@id"
        try:
            ids = [
                id_data_type(
                    urllib.parse.unquote(i[id_field].rstrip("/").split("/").pop())
                )
                for i in event_list
                if i and isinstance(i, dict) and i.get(id_field, None)  # noqa E127
            ]  # noqa E127
        except (ValueError, AttributeError):
            raise serializers.ValidationError(
                {
                    key: _("Invalid value given for %(id_field)s")
                    % {"id_field": id_field}
                }
            )

        return ids

    def cache_related_fields_to_context(self, request):
        events = request.data
        if not isinstance(request.data, list):
            events = [events]

        keywords = Keyword.objects.none()
        locations = Place.objects.none()
        images = Image.objects.none()
        sub_events = Event.objects.none()
        keyword_ids = []
        location_ids = []
        image_ids = []
        subevent_ids = []
        for event in events:
            keyword_ids.extend(self._retrieve_ids("keywords", event))
            keyword_ids.extend(self._retrieve_ids("audience", event))
            location_ids.extend(self._retrieve_ids("location", event))
            image_ids.extend(self._retrieve_ids("images", event, id_data_type=int))
            subevent_ids.extend(self._retrieve_ids("sub_events", event))
        if location_ids:
            locations = Place.objects.filter(id__in=location_ids)
        if keyword_ids:
            keywords = Keyword.objects.filter(id__in=keyword_ids)
        if image_ids:
            images = Image.objects.filter(id__in=image_ids)
        if subevent_ids:
            sub_events = Event.objects.filter(id__in=subevent_ids)

        return {
            "keywords": keywords,
            "location": locations,
            "image": images,
            "sub_events": sub_events,
        }

    def perform_create(self, serializer):
        if isinstance(serializer.validated_data, list):
            event_data_list = serializer.validated_data
        else:
            event_data_list = [serializer.validated_data]

        for event_data in event_data_list:
            _, org = self.user_data_source_and_organization
            if "publisher" in event_data:
                org = event_data["publisher"]
            if not self.request.user.can_create_event(
                org, event_data["publication_status"]
            ):
                raise DRFPermissionDenied()

        super().perform_create(serializer)

    @extend_schema(
        summary="Delete an event",
        description="Event can be deleted if the user has appropriate access permissions.",
        responses={
            204: OpenApiResponse(
                description="Event has been successfully deleted.",
            ),
            **get_common_api_error_responses(excluded_codes=[400]),
            404: OpenApiResponse(
                description="Event was not found.",
            ),
        },
    )
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if not self.request.user.can_edit_event(
            instance.publisher, instance.publication_status, instance.created_by
        ):
            raise DRFPermissionDenied()

        try:
            instance.soft_delete()
        except WebStoreAPIError as exc:
            raise serializers.ValidationError(exc.messages)

    @extend_schema(
        summary="Retrieve information for a single event",
        auth=[],
        responses={
            200: OpenApiResponse(
                EventSerializer,
                description="Event record.",
            ),
            **get_common_api_error_responses(excluded_codes=[400, 401]),
            404: OpenApiResponse(
                description="Event was not found.",
            ),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        try:
            event = Event.objects.get(pk=kwargs["pk"])
        except Event.DoesNotExist:
            raise Http404()
        if event.replaced_by:
            event = event.get_replacement()
            return HttpResponsePermanentRedirect(
                reverse("event-detail", kwargs={"pk": event.pk}, request=request)
            )
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Return a list of events",
        description=render_to_string("swagger/event_list_description.html"),
        auth=[],
        parameters=[
            OpenApiParameter(
                name="x_full_text",
                exclude=True,
            ),
            OpenApiParameter(
                name="x_ongoing",
                exclude=True,
            ),
            OpenApiParameter(
                name="local_ongoing_AND",
                type=OpenApiTypes.STR,
                description=(
                    "Search for local events that are upcoming or have not ended yet. "
                    "Multiple search terms are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="local_ongoing_OR",
                type=OpenApiTypes.STR,
                description=(
                    "Search for local events that are upcoming or have not ended yet. "
                    "Multiple search terms are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="internet_ongoing_AND",
                type=OpenApiTypes.STR,
                description=(
                    "Search for internet events that are upcoming or have not ended yet. "
                    "Multiple search terms are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="internet_ongoing_OR",
                type=OpenApiTypes.STR,
                description=(
                    "Search for internet events that are upcoming or have not ended yet. "
                    "Multiple search terms are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="all_ongoing_AND",
                type=OpenApiTypes.STR,
                description=(
                    "Search for local and internet events that are upcoming or have not ended yet. "
                    "Multiple search terms are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="all_ongoing_OR",
                type=OpenApiTypes.STR,
                description=(
                    "Search for local and internet events that are upcoming or have not ended yet. "
                    "Multiple search terms are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="internet_based",
                type=OpenApiTypes.BOOL,
                description="Search only for events that happen in the internet.",
            ),
            OpenApiParameter(
                name="start",
                type=OpenApiTypes.DATETIME,
                description=(
                    "Search for events beginning or ending after this time. Dates can be "
                    "specified using ISO 8601 (for example, '2024-01-12') and additionally "
                    "<code>today</code> and <code>now</code>."
                ),
            ),
            OpenApiParameter(
                name="end",
                type=OpenApiTypes.DATETIME,
                description=(
                    "Search for events beginning or ending before this time. Dates can be "
                    "specified using ISO 8601 (for example, '2024-01-12') and additionally "
                    "<code>today</code> and <code>now</code>."
                ),
            ),
            OpenApiParameter(
                name="days",
                type=OpenApiTypes.INT,
                description=(
                    "Search for events that intersect with the current time and specified "
                    "amount of days from current time."
                ),
            ),
            OpenApiParameter(
                name="starts_after",
                type=OpenApiTypes.STR,
                description="Search for the events that start after certain time.",
            ),
            OpenApiParameter(
                name="starts_before",
                type=OpenApiTypes.STR,
                description="Search for the events that start before certain time.",
            ),
            OpenApiParameter(
                name="ends_after",
                type=OpenApiTypes.STR,
                description="Search for the events that end after certain time.",
            ),
            OpenApiParameter(
                name="ends_before",
                type=OpenApiTypes.STR,
                description="Search for the events that end before certain time.",
            ),
            OpenApiParameter(
                name="min_duration",
                type=OpenApiTypes.INT,
                description=(
                    "Search for events that are longer than given time in seconds."
                ),
            ),
            OpenApiParameter(
                name="max_duration",
                type=OpenApiTypes.INT,
                description=(
                    "Search for events that are shorter than given time in seconds."
                ),
            ),
            OpenApiParameter(
                name="bbox",
                type={"type": "array", "items": {"type": "string"}},
                description=(
                    "Search for events that are within this bounding box. Decimal coordinates "
                    "are given in order west, south, east, north. Period is used as decimal "
                    "separator. Coordinate system is EPSG:4326."
                ),
            ),
            OpenApiParameter(
                name="location",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events in given locations as specified by id. "
                    "Multiple ids are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="dwithin_origin",
                type={"type": "array", "items": {"type": "string"}},
                description=(
                    "To restrict the retrieved events to a certain distance from a point, use "
                    "the query parameters <code>dwithin_origin</code> and "
                    "<code>dwithin_metres</code> in the format "
                    "<code>dwithin_origin=lon,lat&dwithin_metres=distance</code>."
                ),
            ),
            OpenApiParameter(
                name="dwithin_meters",
                type=OpenApiTypes.INT,
                description=(
                    "To restrict the retrieved events to a certain distance from a point, use "
                    "the query parameters <code>dwithin_origin</code> and "
                    "<code>dwithin_metres</code> in the format "
                    "<code>dwithin_origin=lon,lat&dwithin_metres=distance</code>."
                ),
            ),
            OpenApiParameter(
                name="keyword",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events with given keywords as specified by id. "
                    "Multiple ids are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="keyword_AND",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events with all given keywords as specified by id. "
                    "Multiple ids are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="keyword!",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events with given keywords not to be present as specified by id. "
                    "Multiple ids are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="keyword_set_AND",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events that contains any of the keywords of defined keyword set. "
                    "Multiple keyword sets are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="keyword_set_OR",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events that contains any of the keywords of defined keyword set. "
                    "Multiple keyword sets are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="last_modified_since",
                type=OpenApiTypes.DATETIME,
                description=(
                    "Search for events that have been modified since or at this time."
                ),
            ),
            OpenApiParameter(
                name="show_deleted",
                type=OpenApiTypes.BOOL,
                description="Include deleted events in the query.",
            ),
            OpenApiParameter(
                name="ids",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events with specific id, separating values by commas if you wish "
                    "to query for several event ids."
                ),
            ),
            OpenApiParameter(
                name="event_status",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events with the specified status in the "
                    "<code>event_status</code> field."
                ),
            ),
            OpenApiParameter(
                name="event_type",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events with the specified type in the <code>type_id</code> field."
                ),
            ),
            OpenApiParameter(
                name="text",
                type=OpenApiTypes.STR,
                description=(
                    "Search (case insensitive) through all multilingual text fields "
                    "(name, description, short_description, info_url) of an event "
                    "(every language). Multilingual fields contain the text that users are "
                    "expected to care about, thus multilinguality is useful discriminator."
                ),
            ),
            OpenApiParameter(
                name="combined_text",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events with exact text match for event text fields but retrieves "
                    "expected keywords on the basis of similarity."
                ),
            ),
            OpenApiParameter(
                name="is_free",
                type=OpenApiTypes.BOOL,
                description=(
                    "Search for events that have a price that is free, or not free."
                ),
            ),
            OpenApiParameter(
                name="language",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events that have data or are organized in this language."
                ),
            ),
            OpenApiParameter(
                name="in_language",
                type=OpenApiTypes.STR,
                description="Search for events that are organized in this language.",
            ),
            OpenApiParameter(
                name="translation",
                type=OpenApiTypes.STR,
                description="Search for events that have data in this language.",
            ),
            OpenApiParameter(
                name="audience_min_age_lt",
                type=OpenApiTypes.INT,
                description=(
                    "Search for events whose minimal age is lower than or equals the "
                    "specified value."
                ),
            ),
            OpenApiParameter(
                name="audience_min_age_gt",
                type=OpenApiTypes.INT,
                description=(
                    "Search for events whose minimal age is greater than or equals the "
                    "specified value."
                ),
            ),
            OpenApiParameter(
                name="audience_max_age_lt",
                type=OpenApiTypes.INT,
                description=(
                    "Search for events whose maximum age is lower than or equals the "
                    "specified value."
                ),
            ),
            OpenApiParameter(
                name="audience_max_age_gt",
                type=OpenApiTypes.INT,
                description=(
                    "Search for events whose maximum age is greater than or equals the "
                    "specified value."
                ),
            ),
            OpenApiParameter(
                name="suitable_for",
                type=OpenApiTypes.INT,
                description=(
                    "Search for events that are suitable for the age or age range specified."
                ),
            ),
            OpenApiParameter(
                name="publisher",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events published by the given organization as specified by id."
                ),
            ),
            OpenApiParameter(
                name="publisher_ancestor",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events published by any suborganization under the given "
                    "organization as specified by id."
                ),
            ),
            OpenApiParameter(
                name="data_source",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events that come from the specified source system."
                ),
            ),
            OpenApiParameter(
                name="registration",
                type=OpenApiTypes.BOOL,
                description="Search for events with or without a registration.",
            ),
            OpenApiParameter(
                name="enrolment_open",
                type=OpenApiTypes.BOOL,
                description=(
                    "Search for events that have connected registrations and have "
                    "places at the event."
                ),
            ),
            OpenApiParameter(
                name="enrolment_open_waitlist",
                type=OpenApiTypes.BOOL,
                description=(
                    "Search for events that have connected registrations and have "
                    "places in the waiting lists."
                ),
            ),
            OpenApiParameter(
                name="registration__remaining_attendee_capacity__gte",
                type=OpenApiTypes.INT,
                description=(
                    "Search for events where the remaining registration attendee capacity is "
                    "greater than or equal to the applied parameter."
                ),
            ),
            OpenApiParameter(
                name="registration__remaining_attendee_capacity__isnull",
                type=OpenApiTypes.BOOL,
                description=(
                    "Search for events where the remaining registration attendee capacity is or "
                    "is not NULL."
                ),
            ),
            OpenApiParameter(
                name="registration__remaining_waiting_list_capacity__gte",
                type=OpenApiTypes.INT,
                description=(
                    "Search for events where the remaining registration waiting_list capacity is "
                    "greater than or equal to the applied parameter."
                ),
            ),
            OpenApiParameter(
                name="registration__remaining_waiting_list_capacity__isnull",
                type=OpenApiTypes.BOOL,
                description=(
                    "Search for events where the remaining registration waiting_list capacity is "
                    "or is not NULL."
                ),
            ),
            OpenApiParameter(
                name="show_all",
                type=OpenApiTypes.BOOL,
                description=(
                    "Search for events that authenticated user can edit, including drafts, "
                    "and public non-editable events."
                ),
            ),
            OpenApiParameter(
                name="publication_status",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events with the given publication status. "
                    "Multiple values are separated by comma."
                ),
            ),
            OpenApiParameter(
                name="admin_user",
                type=OpenApiTypes.BOOL,
                description=(
                    "Search for events that authenticated user can edit, including drafts, "
                    "but no other public events."
                ),
            ),
            OpenApiParameter(
                name="created_by",
                type=OpenApiTypes.BOOL,
                description="Search for events created by the authenticated user.",
            ),
            IncludeOpenApiParameter(),
            OpenApiParameter(
                name="sort",
                type=OpenApiTypes.STR,
                description=(
                    "Sort the returned events in the given order. Possible sorting criteria are "
                    "<code>start_time</code>, <code>end_time</code>, <code>name</code>, "
                    "<code>duration</code>, <code>last_modified_time</code>, "
                    "<code>enrolment_start_time</code>, <code>enrolment_end_time</code>, "
                    "<code>registration__enrolment_start_time</code>, "
                    "<code>registration__enrolment_end_time</code>, <code>enrolment_start</code> "
                    "and <code>enrolment_end</code>. The default ordering is "
                    "<code>-last_modified_time</code>."
                ),
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        # docx renderer has additional requirements for listing events
        if request.accepted_renderer.format == "docx":
            if not request.query_params.get("location"):
                raise ParseError(
                    {"detail": _("Must specify a location when fetching DOCX file.")}
                )
            queryset = self.filter_queryset(self.get_queryset())
            if queryset.count() == 0:
                raise ParseError({"detail": _("No events.")})
            if len(set([event.location for event in queryset])) > 1:
                raise ParseError({"detail": _("Only one location allowed.")})
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        # Switch to normal renderer for docx errors.
        response = super().finalize_response(request, response, *args, **kwargs)
        # Prevent rendering errors as DOCX files
        if response.status_code != 200 and request.accepted_renderer.format == "docx":
            first_renderer = self.renderer_classes[0]()
            response.accepted_renderer = first_renderer
            response.accepted_media_type = first_renderer.media_type

        return response


register_view(EventViewSet, "event")


DATE_DECAY_SCALE = "30d"


class SearchViewSet(
    JSONAPIViewMixin,
    GeoModelAPIView,
    viewsets.ViewSetMixin,
    AuditLogApiViewMixin,
    generics.ListAPIView,
):
    queryset = Event.objects.none()  # For automated Swagger schema generation.

    def get_serializer_class(self):
        if self.request.version == "v0.1":
            return SearchSerializerV0_1
        return SearchSerializer

    @extend_schema(
        summary="Search through events and places",
        description=render_to_string("swagger/search_list_description.html"),
        auth=[],
        parameters=[
            OpenApiParameter(
                name="type",
                type=OpenApiTypes.STR,
                description=(
                    "Comma-separated list of resource types to search for. Currently allowed "
                    "values are <code>event</code> and <code>place</code>. <code>type=event</code> "
                    "must be specified for event date filtering and relevancy sorting."
                ),
            ),
            OpenApiParameter(
                name="q",
                type=OpenApiTypes.STR,
                description=(
                    "Search for events and places matching this string. Mutually exclusive with "
                    "<code>input</code> typeahead search."
                ),
            ),
            OpenApiParameter(
                name="input",
                type=OpenApiTypes.STR,
                description=(
                    "Return autocompletition suggestions for this string. Mutually exclusive with "
                    "<code>q</code> full-text search."
                ),
            ),
            OpenApiParameter(
                name="start",
                type=OpenApiTypes.DATETIME,
                description=(
                    "Search for events beginning or ending after this time. Dates can be "
                    "specified using ISO 8601 (for example, '2024-01-12') and additionally "
                    "<code>today</code> and <code>now</code>."
                ),
            ),
            OpenApiParameter(
                name="end",
                type=OpenApiTypes.DATETIME,
                description=(
                    "Search for events beginning or ending before this time. Dates can be "
                    "specified using ISO 8601 (for example, '2024-01-12') and additionally "
                    "<code>today</code> and <code>now</code>."
                ),
            ),
        ],
        responses={
            200: OpenApiResponse(
                EventSerializer(many=True),
                description="List of resources.",
            ),
        },
    )
    def list(self, request, *args, **kwargs):
        languages = get_fixed_lang_codes()
        default_language = languages[0] if languages else None

        # If the incoming language is not specified, go with the default.
        self.lang_code = request.query_params.get("language", default_language)
        if self.lang_code not in languages:
            raise ParseError(
                "Invalid language supplied. Supported languages: %s"
                % ",".join(languages)
            )

        params = request.query_params

        input_val = params.get("input", "").strip()
        q_val = params.get("q", "").strip()
        if not input_val and not q_val:
            raise ParseError(
                "Supply search terms with 'q=' or autocomplete entry with 'input='"
            )
        if input_val and q_val:
            raise ParseError("Supply either 'q' or 'input', not both")

        old_language = translation.get_language()[:2]
        translation.activate(self.lang_code)

        queryset = SearchQuerySet()
        if input_val:
            queryset = queryset.autocomplete(autosuggest=input_val)
        else:
            queryset = queryset.filter(text=AutoQuery(q_val))

        models = None
        types = params.get("type", "").split(",")
        if types:
            models = set()
            for t in types:
                if t == "event":
                    models.add(Event)
                elif t == "place":
                    models.add(Place)

        if self.request.version == "v0.1" and len(models) == 0:
            models.add(Event)

        if len(models) == 1 and Event in models:
            division = params.get("division", None)
            if division:
                queryset = filter_division(
                    queryset, "location__divisions", division.split(",")
                )

            start = params.get("start", None)
            if start:
                dt = utils.parse_time(start)[0]
                queryset = queryset.filter(Q(end_time__gt=dt) | Q(start_time__gte=dt))

            end = params.get("end", None)
            if end:
                dt = utils.parse_end_time(end)[0]
                queryset = queryset.filter(Q(end_time__lt=dt) | Q(start_time__lte=dt))

            if not start and not end and hasattr(queryset.query, "add_decay_function"):
                # If no time-based filters are set, make the relevancy score
                # decay the further in the future the event is.
                now = datetime.utcnow()
                queryset = queryset.filter(end_time__gt=now).decay(
                    {"gauss": {"end_time": {"origin": now, "scale": DATE_DECAY_SCALE}}}
                )

        if len(models) == 1 and Place in models:
            division = params.get("division", None)
            if division:
                queryset = filter_division(queryset, "divisions", division.split(","))

        if len(models) > 0:
            queryset = queryset.models(*list(models))

        self.object_list = queryset.load_all()

        page = self.paginate_queryset(self.object_list)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            resp = self.get_paginated_response(serializer.data)
            translation.activate(old_language)
            return resp

        serializer = self.get_serializer(self.object_list, many=True)
        resp = Response(serializer.data)

        translation.activate(old_language)

        return resp


register_view(SearchViewSet, "search", base_name="search")


@extend_schema(exclude=True)
class FeedbackViewSet(
    AuditLogApiViewMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = FeedbackSerializer


register_view(FeedbackViewSet, "feedback", base_name="feedback")


@extend_schema(exclude=True)
class GuestFeedbackViewSet(
    AuditLogApiViewMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = FeedbackSerializer
    permission_classes = (GuestPost,)


register_view(GuestFeedbackViewSet, "guest-feedback", base_name="guest-feedback")
