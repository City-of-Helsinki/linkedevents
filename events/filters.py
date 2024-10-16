from datetime import datetime
from datetime import timezone as datetime_timezone
from functools import partial
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import django_filters
from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Case, Exists, F, OuterRef, Q, When
from django.db.models import DateTimeField as ModelDateTimeField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization
from munigeo.api import srid_to_srs
from rest_framework import serializers
from rest_framework.exceptions import ParseError

from events.models import Event, Place
from events.widgets import DistanceWithinWidget
from linkedevents.filters import LinkedEventsOrderingFilter


def _annotate_queryset_for_filtering_by_enrolment_start_or_end(
    queryset, ordering, order_field_name: str, db_field_name: str
):
    if order_field_name in ordering:
        # Put events with null enrolment times to the end of the list for
        # the ascending ordering.
        events_with_null_times_last = timezone.datetime.max.replace(
            tzinfo=timezone.get_default_timezone()
        )
    else:
        # Put events with null enrolment times to the end of the list for
        # the descending ordering.
        events_with_null_times_last = timezone.datetime.min.replace(
            tzinfo=datetime_timezone.utc
        )
        order_field_name = order_field_name.removeprefix("-")

    return queryset.annotate(
        **{
            f"{order_field_name}": Case(
                When(
                    **{
                        f"registration__{db_field_name}__isnull": False,
                    },
                    then=F(f"registration__{db_field_name}"),
                ),
                When(
                    **{
                        f"{db_field_name}__isnull": True,
                        f"registration__{db_field_name}__isnull": True,
                    },
                    then=events_with_null_times_last,
                ),
                default=F(f"{db_field_name}"),
                output_field=ModelDateTimeField(),
            ),
        }
    )


def _in_or_null_filter(field_name, queryset, name, value):
    """
    Supports filtering objects by several values in the same field; null or none will trigger
    isnull filter.
    """  # noqa: E501
    q = Q()

    if "null" in value or "none" in value:
        null_query = {field_name + "__isnull": True}
        q = q | Q(**null_query)
        if "null" in value:
            value.remove("null")
        if "none" in value:
            value.remove("none")

    if value:
        in_query = {field_name + "__in": value}
        q = q | Q(**in_query)

    return queryset.filter(q)


def filter_division(queryset, name: str, value: Iterable[str]):
    """
    Allows division filtering by both division name and more specific ocd id (identified by colon
    in the parameter)

    Depending on the deployment location, offers simpler filtering by appending
    country and municipality information to ocd ids.

    Examples:
        /event/?division=kamppi
        will match any and all divisions with the name Kamppi, regardless of their type.

        /event/?division=ocd-division/country:fi/kunta:helsinki/osa-alue:kamppi
        /event/?division=ocd-division/country:fi/kunta:helsinki/suurpiiri:kamppi
        will match different division types with the otherwise identical id kamppi.

        /event/?division=osa-alue:kamppi
        /event/?division=suurpiiri:kamppi
        will match different division types with the id kamppi, if correct country and municipality
        information is
        present in settings.

        /event/?division=helsinki
        will match any and all divisions with the name Helsinki, regardless of their type.

        /event/?division=ocd-division/country:fi/kunta:helsinki
        will match the Helsinki municipality.

        /event/?division=kunta:helsinki
        will match the Helsinki municipality, if correct country information is present in settings.

    """  # noqa: E501

    ocd_ids = []
    names = []

    for item in value:
        if ":" in item:
            # we have a munigeo division
            if hasattr(settings, "MUNIGEO_MUNI") and hasattr(
                settings, "MUNIGEO_COUNTRY"
            ):
                # append ocd path if we have deployment information
                if not item.startswith("ocd-division"):
                    if not item.startswith("country"):
                        if not item.startswith("kunta"):
                            item = settings.MUNIGEO_MUNI + "/" + item
                        item = settings.MUNIGEO_COUNTRY + "/" + item
                    item = "ocd-division/" + item
            ocd_ids.append(item)
        else:
            # we assume human name
            names.append(item.title())

    if hasattr(queryset, "distinct"):
        # do the join with Q objects (not querysets) in case the queryset has
        # extra fields that would crash qs join
        query = Q(**{name + "__ocd_id__in": ocd_ids}) | Q(
            **{name + "__translations__name__in": names}
        )
        return queryset.filter(
            Exists(queryset.model.objects.filter(query, pk=OuterRef("pk")))
        ).prefetch_related(name + "__translations")
    else:
        # Haystack SearchQuerySet does not support distinct, so we only support
        # one type of search at a time:
        if ocd_ids:
            return queryset.filter(**{name + "__ocd_id__in": ocd_ids})
        else:
            return queryset.filter(**{name + "__name__in": names})


class EventOrderingFilter(LinkedEventsOrderingFilter):
    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            ordering = []

        if "duration" in ordering or "-duration" in ordering:
            queryset = queryset.extra(select={"duration": "end_time - start_time"})

        if "enrolment_start" in ordering or "-enrolment_start" in ordering:
            queryset = _annotate_queryset_for_filtering_by_enrolment_start_or_end(
                queryset, ordering, "enrolment_start", "enrolment_start_time"
            )

        if "enrolment_end" in ordering or "-enrolment_end" in ordering:
            queryset = _annotate_queryset_for_filtering_by_enrolment_start_or_end(
                queryset, ordering, "enrolment_end", "enrolment_end_time"
            )

        return super().filter_queryset(request, queryset, view)


class EventFilter(django_filters.rest_framework.FilterSet):
    division = django_filters.Filter(
        field_name="location__divisions",
        widget=django_filters.widgets.CSVWidget(),
        method=filter_division,
        help_text=_(
            "You may filter events by specific OCD division id, or by division name. "
            "The latter query checks all divisions with the name, regardless of division type."  # noqa: E501
        ),
    )
    super_event_type = django_filters.Filter(
        field_name="super_event_type",
        widget=django_filters.widgets.CSVWidget(),
        method=partial(_in_or_null_filter, "super_event_type"),
        help_text=_(
            "Search for events with the given superevent type, including none. "
            "Multiple types are separated by comma."
        ),
    )
    super_event = django_filters.Filter(
        field_name="super_event",
        widget=django_filters.widgets.CSVWidget(),
        method=partial(_in_or_null_filter, "super_event"),
        help_text=_(
            "Search for events with the given superevent as specified by id, including none. "  # noqa: E501
            "Multiple ids are separated by comma."
        ),
    )
    dwithin = django_filters.Filter(
        method="filter_dwithin", widget=DistanceWithinWidget()
    )
    maximum_attendee_capacity_gte = django_filters.NumberFilter(
        field_name="maximum_attendee_capacity",
        lookup_expr="gte",
        help_text=_(
            "Search for events with maximum attendee capacity greater than or equal the "  # noqa: E501
            "applied parameter."
        ),
    )
    minimum_attendee_capacity_gte = django_filters.NumberFilter(
        field_name="minimum_attendee_capacity",
        lookup_expr="gte",
        help_text=_(
            "Search for events with minimum attendee capacity greater than or equal the "  # noqa: E501
            "applied parameter."
        ),
    )
    maximum_attendee_capacity_lte = django_filters.NumberFilter(
        field_name="maximum_attendee_capacity",
        lookup_expr="lte",
        help_text=_(
            "Search for events events with maximum attendee capacity less than or equal the "  # noqa: E501
            "applied parameter."
        ),
    )
    minimum_attendee_capacity_lte = django_filters.NumberFilter(
        field_name="minimum_attendee_capacity",
        lookup_expr="lte",
        help_text=_(
            "Search for events events with minimum attendee capacity less than or equal the "  # noqa: E501
            "applied parameter."
        ),
    )
    hide_recurring_children = django_filters.BooleanFilter(
        method="filter_hide_recurring_children",
        help_text=_(
            "Hide all child events for super events which are of type <code>recurring</code>."  # noqa: E501
        ),
    )

    x_full_text = django_filters.CharFilter(method="filter_x_full_text")

    x_ongoing = django_filters.BooleanFilter(method="filter_x_ongoing")

    registration_admin_user = django_filters.BooleanFilter(
        method="filter_registration_admin_user",
        help_text=_("Search for events whose registration the user can modify."),
    )

    enrolment_open_on = django_filters.DateTimeFilter(
        method="filter_enrolment_open_on",
        help_text=_(
            "Search for events where enrolment is open on a given date or datetime."
        ),
    )

    class Meta:
        model = Event
        fields = {
            "registration__remaining_attendee_capacity": ["gte", "isnull"],
            "registration__remaining_waiting_list_capacity": ["gte", "isnull"],
        }

    def filter_enrolment_open_on(self, queryset, name, value: datetime):
        value = value.astimezone(ZoneInfo(settings.TIME_ZONE))

        queryset = _annotate_queryset_for_filtering_by_enrolment_start_or_end(
            queryset, [], "-enrolment_start", "enrolment_start_time"
        )
        queryset = _annotate_queryset_for_filtering_by_enrolment_start_or_end(
            queryset, ["enrolment_end"], "enrolment_end", "enrolment_end_time"
        )

        return queryset.filter(enrolment_start__lte=value, enrolment_end__gte=value)

    def filter_dwithin(self, queryset, name, value: tuple[tuple[str, str], str]):
        srs = srid_to_srs(self.request.query_params.get("srid"))
        origin, metres = value
        if not (origin and metres):
            # Need both values for filtering
            return queryset

        try:
            origin_x, origin_y = [float(i) for i in origin]
        except ValueError:
            raise ParseError("Origin must be a tuple of two numbers")
        try:
            metres = float(metres)
        except ValueError:
            raise ParseError("Metres must be a number")

        places = Place.objects.filter(
            position__dwithin=(
                Point(origin_x, origin_y, srid=srs.srid),
                D(m=metres),
            )
        )

        return queryset.filter(location__in=places)

    def filter_hide_recurring_children(self, queryset, name, value: Optional[bool]):
        if not value:
            return queryset

        # There are two different structures that can define a super event
        # for recurring events.
        return queryset.exclude(
            super_event__super_event_type=Event.SuperEventType.RECURRING
        ).exclude(
            eventaggregatemember__event_aggregate__super_event__super_event_type=Event.SuperEventType.RECURRING
        )

    def filter_x_full_text(self, qs, name, value: Optional[str]):
        if not value:
            return qs

        language = self.request.query_params.get("x_full_text_language", "fi")
        if language not in ["fi", "en", "sv"]:
            raise serializers.ValidationError(
                {
                    "x_full_text_language": _(
                        "x_full_text supports the following languages: fi, en, sv"
                    )
                }
            )

        config_map = {
            "fi": "finnish",
            "en": "english",
            "sv": "swedish",
        }
        search_vector_name = f"full_text__search_vector_{language}"
        search_query = SearchQuery(
            value, search_type="websearch", config=config_map[language]
        )
        search_rank = SearchRank(F(search_vector_name), search_query)

        # Warning: order matters, annotate should follow filter
        # Otherwise Django creates a redundant LEFT OUTER JOIN for sorting
        return (
            qs.filter(**{search_vector_name: search_query})
            .annotate(rank=search_rank)
            .order_by("-rank")
        )

    def filter_x_ongoing(self, qs, name, ongoing: Optional[bool]):
        if ongoing is None:
            return qs

        if ongoing:
            return qs.filter(end_time__gt=datetime.now(datetime_timezone.utc))

        return qs.filter(end_time__lte=datetime.now(datetime_timezone.utc))

    def filter_registration_admin_user(self, queryset, name, value):
        if not value:
            return queryset

        if self.request.user.is_authenticated:
            # displays all events whose registration the user can modify
            return self.request.user.get_editable_events_for_registration(queryset)
        else:
            return queryset.none()


class OrganizationFilter(django_filters.rest_framework.FilterSet):
    dissolved = django_filters.BooleanFilter(
        method="filter_dissolved",
        help_text=_(
            "Get or exclude dissolved organizations; <code>true</code> shows only dissolved and "  # noqa: E501
            "<code>false</code> excludes dissolved organizations."
        ),
    )

    class Meta:
        model = Organization
        fields = ("dissolved",)

    def filter_dissolved(self, queryset, name, value: Optional[bool]):
        today = timezone.localdate()

        if value:
            return queryset.filter(dissolution_date__lte=today)

        return queryset.filter(
            Q(dissolution_date__gt=today) | Q(dissolution_date__isnull=True)
        )


class PlaceFilter(django_filters.rest_framework.FilterSet):
    division = django_filters.Filter(
        field_name="divisions",
        lookup_expr="in",
        widget=django_filters.widgets.CSVWidget(),
        method="filter_divisions",
        help_text=_(
            "You may filter places by specific OCD division id, or by division name. "
            "The latter query checks all divisions with the name, regardless of division type."  # noqa: E501
        ),
    )

    class Meta:
        model = Place
        fields = ("division",)

    def filter_divisions(self, queryset, name, value):
        return filter_division(queryset, name, value)
