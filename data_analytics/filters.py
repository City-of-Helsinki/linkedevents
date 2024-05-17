import django_filters
from django_orghierarchy.models import Organization
from munigeo.models import AdministrativeDivision

from events.models import Event, Keyword, Place
from events.utils import parse_time
from registrations.models import Registration, SignUp


class DataAnalyticsLastModifiedTimeBaseFilter(django_filters.rest_framework.FilterSet):
    _LAST_MODIFIED_FIELD = "last_modified_time"

    last_modified_gte = django_filters.CharFilter(method="filter_last_modified_gte")

    def filter_last_modified_gte(self, queryset, name, value: str):
        dt = parse_time(value)[0]
        return queryset.filter(**{f"{self._LAST_MODIFIED_FIELD}__gte": dt})


class DataAnalyticsAdministrativeDivisionFilter(
    DataAnalyticsLastModifiedTimeBaseFilter
):
    _LAST_MODIFIED_FIELD = "modified_at"

    class Meta:
        model = AdministrativeDivision
        fields = ()


class DataAnalyticsOrganizationFilter(DataAnalyticsLastModifiedTimeBaseFilter):
    class Meta:
        model = Organization
        fields = ()


class DataAnalyticsPlaceFilter(DataAnalyticsLastModifiedTimeBaseFilter):
    class Meta:
        model = Place
        fields = ()


class DataAnalyticsKeywordFilter(DataAnalyticsLastModifiedTimeBaseFilter):
    class Meta:
        model = Keyword
        fields = ()


class DataAnalyticsEventFilter(DataAnalyticsLastModifiedTimeBaseFilter):
    class Meta:
        model = Event
        fields = ()


class DataAnalyticsRegistrationFilter(DataAnalyticsLastModifiedTimeBaseFilter):
    class Meta:
        model = Registration
        fields = ()


class DataAnalyticsSignUpFilter(DataAnalyticsLastModifiedTimeBaseFilter):
    class Meta:
        model = SignUp
        fields = ()
