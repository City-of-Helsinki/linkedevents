import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from functools import partial
from zoneinfo import ZoneInfo

import django_filters
from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.exceptions import ImproperlyConfigured
from django.db.models import (
    BooleanField,
    Case,
    DurationField,
    Exists,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    When,
)
from django.db.models import DateTimeField as ModelDateTimeField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization
from munigeo.api import srid_to_srs
from rest_framework import serializers
from rest_framework.exceptions import ParseError

from events import utils
from events.models import Event, EventAggregate, Place
from events.search_index.utils import extract_word_bases
from events.widgets import DistanceWithinWidget
from linkedevents.filters import LinkedEventsOrderingFilter
from linkedevents.utils import get_fixed_lang_codes

languages = get_fixed_lang_codes()


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
        events_with_null_times_last = timezone.datetime.min.replace(tzinfo=UTC)
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


def parse_duration_string(duration) -> timedelta:
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

    return timedelta(seconds=int(val) * mul)


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
    @classmethod
    def check_filter_order(cls):
        """Class method to validate that the hide_recurring_children filter is placed
        in last. It needs to be placed in last to be able to apply all selected filters
        to sub events.
        """

        filters = list(cls.declared_filters.keys())
        if filters[-1] != "hide_recurring_children":
            raise ImproperlyConfigured(
                "Hide recurring children must be the last filter to be able to apply "
                "other filters to sub-events."
            )

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
    hide_super_event = django_filters.BooleanFilter(
        method="filter_hide_super_event",
        help_text=_("Hide all events which are super events."),
    )

    full_text = django_filters.CharFilter(method="filter_full_text")

    ongoing = django_filters.BooleanFilter(method="filter_ongoing")

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
    min_duration = django_filters.CharFilter(
        method="filter_min_duration",
        help_text=_("Search for events that are at least as long as given duration."),
    )
    max_duration = django_filters.CharFilter(
        method="filter_max_duration",
        help_text=_(
            "Search for events that are at most as long as the given duration."
        ),
    )
    weekday = django_filters.MultipleChoiceFilter(
        choices=settings.ISO_WEEKDAYS,
        method="filter_weekday",
        distinct=False,
        widget=django_filters.widgets.CSVWidget(),
        help_text=_("Filter events by their occurring weekday using iso format."),
    )

    days = django_filters.CharFilter(
        method="filter_days",
        help_text=_(
            "Search for events that intersect with the current time and specified "
            "amount of days from current time."
        ),
    )

    start = django_filters.CharFilter(
        method="filter_start",
        help_text=_(
            "Search for events beginning or ending after this time. Dates can be "
            "specified using ISO 8601 (for example, '2024-01-12') and additionally "
            "`today` and `now`."
        ),
    )

    end = django_filters.CharFilter(
        method="filter_end",
        help_text=_(
            "Search for events beginning or ending before this time. Dates can be "
            "specified using ISO 8601 (for example, '2024-01-12') and additionally "
            "`today` and `now`."
        ),
    )

    hide_recurring_children_sub_events = django_filters.BooleanFilter(
        required=False,
        help_text=_(
            "Extension filter to hide_recurring_children. If set to true, "
            "filtering will also consider events' sub-events."
        ),
        method="filter_hide_recurring_children_sub_events",
    )

    # Must be the last defined filter so that can include sub-events.
    hide_recurring_children = django_filters.BooleanFilter(
        method="filter_hide_recurring_children",
        help_text=_(
            "Hide all child events for super events which are of type <code>recurring</code>."  # noqa: E501
        ),
    )

    class Meta:
        model = Event
        fields = {
            "registration__remaining_attendee_capacity": ["gte", "isnull"],
            "registration__remaining_waiting_list_capacity": ["gte", "isnull"],
        }

    def filter_weekday(self, queryset, name, values):
        if not values:
            return queryset

        weekdays = [int(i) for i in values]

        # Add some utility fields to the queryset for filtering.
        queryset = queryset.annotate(
            duration=ExpressionWrapper(
                F("end_time") - F("start_time"), output_field=DurationField()
            ),
            start_day=F("start_time__iso_week_day"),
            end_day=F("end_time__iso_week_day"),
            spans_over_weekend=Case(
                When(start_day__gt=F("end_day"), then=True),
                default=False,
                output_field=BooleanField(),
            ),
            over_week_long_event=Case(
                When(duration__gte=timedelta(days=7), then=True),
                default=False,
            ),
        )

        # Basic check for start and end time days.
        weekday_filter = Q(start_day__in=weekdays) | Q(end_day__in=weekdays)

        # Over week long events are always included.
        weekday_filter |= Q(over_week_long_event=True)
        for weekday in weekdays:
            weekday_filter |= Q(
                Q(spans_over_weekend=True, over_week_long_event=False)
                & Q(Q(start_day__lte=weekday) | Q(end_day__gte=weekday))
            )

            weekday_filter |= Q(
                Q(
                    spans_over_weekend=False,
                    over_week_long_event=False,
                    start_day__lte=weekday,
                    end_day__gte=weekday,
                )
            )

        return queryset.filter(weekday_filter)

    def filter_max_duration(self, queryset, name, value):
        if not value:
            return queryset

        max_duration = parse_duration_string(value)
        return queryset.annotate(
            duration=ExpressionWrapper(
                F("end_time") - F("start_time"), output_field=DurationField()
            )
        ).filter(duration__lte=max_duration)

    def filter_min_duration(self, queryset, name, value):
        if not value:
            return queryset

        min_duration = parse_duration_string(value)
        return queryset.annotate(
            duration=ExpressionWrapper(
                F("end_time") - F("start_time"), output_field=DurationField()
            )
        ).filter(duration__gte=min_duration)

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

    def filter_hide_super_event(self, queryset, name, value: bool | None):
        if not value:
            return queryset

        return queryset.exclude(
            Q(super_event__isnull=True) & Q(super_event_type__isnull=False)
            | Exists(EventAggregate.objects.filter(super_event=OuterRef("pk")))
        )

    def filter_full_text(self, qs, name, value: str | None):
        if not value:
            return qs

        language = self.request.query_params.get("full_text_language", "fi")
        if language not in languages:
            raise serializers.ValidationError(
                {
                    "full_text_language": _(
                        f"full_text supports the following "
                        f"languages: {', '.join(languages)}"
                    )
                }
            )
        # replace non-word characters with space
        search_value = re.sub(r"\W", " ", value)
        words = []
        extract_word_bases(search_value, words, language)
        search_value = " ".join(words)
        search_vector_name = f"full_text__search_vector_{language}"
        search_query = SearchQuery(
            search_value, search_type="websearch", config="simple"
        )

        qs = qs.filter(**{search_vector_name: search_query})
        sort = self.request.query_params.get("sort", "")
        if not sort:
            # default to search rank if no other sorting is defined
            search_rank = SearchRank(F(search_vector_name), search_query)
            # Warning: order matters, annotate should follow filter
            # Otherwise Django creates a redundant LEFT OUTER JOIN for sorting
            return qs.annotate(rank=search_rank).order_by("-rank", "id")
        else:
            return qs

    def filter_ongoing(self, qs, name, ongoing: bool | None):
        if ongoing is None:
            return qs

        if ongoing:
            return qs.filter(end_time__gt=datetime.now(UTC))

        return qs.filter(end_time__lte=datetime.now(UTC))

    def filter_registration_admin_user(self, queryset, name, value):
        if not value:
            return queryset

        if self.request.user.is_authenticated:
            # displays all events whose registration the user can modify
            return self.request.user.get_editable_events_for_registration(queryset)
        else:
            return queryset.none()

    def filter_days(self, queryset, name, value):
        try:
            days = int(value)
        except ValueError:
            raise ParseError(_("Error while parsing days."))
        if days < 1:
            raise serializers.ValidationError(_("Days must be 1 or more."))
        if "start" in self.data or "end" in self.data:
            raise serializers.ValidationError(
                _("Start or end cannot be used with days.")
            )

        today = datetime.now(UTC).date()

        start = today.isoformat()
        end = (today + timedelta(days=days)).isoformat()

        queryset = self.filter_start(queryset, "start", start)
        queryset = self.filter_end(queryset, "end", end)
        return queryset

    def filter_start(self, queryset, name, value):
        if "end" not in self.data:
            # postponed events are considered to be "far" in the future and should be
            # included if end is *not* given
            postponed_q = Q(event_status=Event.Status.POSTPONED)
        else:
            postponed_q = Q()

        # Inconsistent behaviour, see test_inconsistent_tz_default
        dt = utils.parse_time(value, default_tz=ZoneInfo(settings.TIME_ZONE))[0]

        # only return events with specified end times, or unspecified start times, during the whole of the event  # noqa: E501
        # this gets of rid pesky one-day events with no known end time (but known
        # start) after they started
        return queryset.filter(
            Q(end_time__gt=dt, has_end_time=True)
            | Q(end_time__gt=dt, has_start_time=False)
            | Q(start_time__gte=dt)
            | postponed_q
        )

    def filter_end(self, queryset, name, value):
        dt = utils.parse_end_time(value, default_tz=ZoneInfo(settings.TIME_ZONE))[0]
        return queryset.filter(Q(end_time__lt=dt) | Q(start_time__lte=dt))

    def filter_hide_recurring_children_sub_events(
        self, queryset, name, value: bool | None
    ):
        """
        This is a boolean filter that determines whether to include sub_events
        matches to results. This is used only with the hide_recurring_children filter,
        and that said, this is an extension of the latter.
        """
        return queryset

    def filter_hide_recurring_children(self, queryset, name, value: bool | None):
        """
        This filter must be applied last so that it can work with
        the hide_recurring_children_sub_events parameter.
        """
        if not value:
            return queryset

        cleaned_data = getattr(self.form, "cleaned_data", None)
        super_events = None
        if cleaned_data and cleaned_data.get(
            "hide_recurring_children_sub_events", False
        ):
            # If sub_events is set to true, we need to include the super events.
            super_events = Event.objects.filter(
                Exists(queryset.filter(super_event=OuterRef("pk")))
                | Exists(
                    queryset.filter(
                        eventaggregatemember__event_aggregate__super_event=OuterRef(
                            "pk"
                        )
                    )
                )
            )

            super_events = super_events.filter(
                Exists(queryset.filter(super_event=OuterRef("pk")))
            )

        # There are two different structures that can define a super event
        # for recurring events.
        queryset = queryset.exclude(
            super_event__super_event_type=Event.SuperEventType.RECURRING
        ).exclude(
            eventaggregatemember__event_aggregate__super_event__super_event_type=Event.SuperEventType.RECURRING
        )

        if super_events:
            return queryset | super_events

        return queryset


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

    def filter_dissolved(self, queryset, name, value: bool | None):
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


EventFilter.check_filter_order()
