import collections
import re
import warnings
from datetime import datetime, timedelta
from typing import Iterable, Optional

import bleach
import pytz
from dateutil.parser import parse as dateutil_parse
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization
from rest_framework.exceptions import ParseError, PermissionDenied

from events.auth import ApiKeyAuth
from events.models import DataSource, Keyword, Place
from events.sql import count_events_for_keywords, count_events_for_places
from helevents.models import User


def convert_to_camelcase(s):
    return "".join(word.title() if i else word for i, word in enumerate(s.split("_")))


def convert_from_camelcase(s):
    return re.sub(
        r"(^|[a-z])([A-Z])", lambda m: "_".join([i.lower() for i in m.groups() if i]), s
    )


def get_value_from_tuple_list(list_of_tuples, search_key, value_index):
    """
    Find "value" from list of tuples by using the other value in tuple as a
    search key and other as a returned value
    :param list_of_tuples: tuples to be searched
    :param search_key: search key used to find right tuple
    :param value_index: Index telling which side of tuple is
                        returned and which is used as a key
    :return: Value from either side of tuple
    """

    for _i, v in enumerate(list_of_tuples):
        if str(v[value_index ^ 1]) == str(search_key):
            return v[value_index]


def update(d, u):
    """
    Recursively update dict d with
    values at all levels of dict u
    """
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            r = update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def recache_n_events(keyword_ids, all=False):
    """
    Recache the number of events for the given keywords (by ID).

    :param all: recache all keywords instead
    :type keyword_ids: Iterable[str]
    """

    # needed so we don't empty the blasted iterator mid-operation
    keyword_ids = tuple(set(keyword_ids))
    with transaction.atomic():
        if all:
            Keyword.objects.update(n_events=0)
        else:
            # set the flag to false here, so zero-event keywords will get it too
            Keyword.objects.filter(id__in=keyword_ids).update(
                n_events=0, n_events_changed=False
            )
        for keyword_id, n_events in count_events_for_keywords(
            keyword_ids, all=all
        ).items():
            Keyword.objects.filter(id=keyword_id).update(n_events=n_events)


def recache_n_events_in_locations(place_ids, all=False):
    """
    Recache the number of events for the given locations (by ID).

    :param all: recache all places instead
    :type place_ids: Iterable[str]
    """

    # needed so we don't empty the blasted iterator mid-operation
    place_ids = tuple(set(place_ids))
    with transaction.atomic():
        if all:
            Place.objects.update(n_events=0)
        else:
            # set the flag to false here, so zero-event places will get it too
            Place.objects.filter(id__in=place_ids).update(
                n_events=0, n_events_changed=False
            )
        for place_id, n_events in count_events_for_places(place_ids, all=all).items():
            Place.objects.filter(id=place_id).update(n_events=n_events)


def parse_time(time_str: str, default_tz=pytz.utc) -> (datetime, bool):
    """
    Parse a time string into a datetime object. Accepts ISO8061,
    date format "YYYY-MM-DD", "today" and "now".

    :param time_str:
    :param default_tz: default timezone to assume for naive datetimes
    :return: a tuple containing the parsed datetime and a boolean indicating
             whether the returned datetime represents a date
    :raises: ParseError
    """
    local_tz = pytz.timezone(settings.TIME_ZONE)
    time_str = time_str.strip()

    if time_str.lower() == "today":
        return start_of_day(timezone.now()), True
    if time_str.lower() == "now":
        return timezone.now(), False

    try:
        return local_tz.localize(datetime.strptime(time_str, "%Y-%m-%d")), True
    except ValueError:
        pass

    try:
        # Handle all other times through dateutil.
        dt = dateutil_parse(time_str)
        # Dateutil may allow dates with too large negative tzoffset, crashing
        # psycopg later
        if dt.tzinfo and abs(dt.tzinfo.utcoffset(dt)) > timedelta(hours=15):
            raise ParseError(f"Time zone given in timestamp {dt} out of bounds.")

        # Based on a previous comment, the original intended behaviour is to
        # use UTC if no timezone is given.
        if is_naive_datetime(dt):
            dt = default_tz.localize(dt)

        return dt, False
    except (TypeError, ValueError, OverflowError):
        raise ParseError("time in invalid format (try ISO 8601 or yyyy-mm-dd)")


def parse_end_time(time_str: str, default_tz=pytz.utc) -> (datetime, bool):
    """
    Parse a time string and if it turns out to be a date, convert it to
    end of day (= start of next day)
    :param time_str:
    :return:
    """
    dt, is_date = parse_time(time_str, default_tz=default_tz)
    if is_date:
        dt = start_of_next_day(dt)
    return dt, is_date


def is_naive_datetime(dt: datetime) -> bool:
    """
    Check if the given datetime is naive (i.e. has no timezone information).
    :param dt: a datetime object
    :return: True if the datetime is naive, False otherwise
    """
    return dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None


def start_of_day(dt: datetime) -> datetime:
    """
    Return the start of the day for the given datetime.
    :param dt: a datetime object
    :return: the earliest aware datetime of the same day (at 00:00:00)
    """
    tz = pytz.timezone(settings.TIME_ZONE)
    return tz.localize(
        dt.astimezone(tz).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        )
    )


def start_of_next_day(dt: datetime) -> datetime:
    """
    Return the start of the day after the given datetime.
    :param dt: a datetime object
    :return: the earliest datetime of the next day (at 00:00:00)
    """
    tz = pytz.timezone(settings.TIME_ZONE)
    return start_of_day(dt.astimezone(tz).replace(tzinfo=None) + timedelta(days=1))


def start_of_previous_day(dt: datetime) -> datetime:
    """
    Return the start of the day before the given datetime
    :param dt: a datetime object
    :return: the earliest aware datetime of the previous day (at 00:00:00)
    """
    tz = pytz.timezone(settings.TIME_ZONE)
    return start_of_day(dt.astimezone(tz).replace(tzinfo=None) - timedelta(days=1))


def get_deleted_object_name():
    return {
        "fi": "POISTETTU",
        "sv": "RADERAD",
        "en": "DELETED",
    }


def get_or_create_default_organization() -> Optional[Organization]:
    """Create (if needed) the default organization to which users can be added if they
    don't belong to any organization.
    """
    if not settings.EXTERNAL_USER_PUBLISHER_ID:
        warnings.warn(
            "EXTERNAL_USER_PUBLISHER_ID is empty, will not set or create "
            "default organization.",
            stacklevel=2,
        )
        return None

    data_source, created = DataSource.objects.get_or_create(
        id=settings.SYSTEM_DATA_SOURCE_ID,
        defaults={
            "user_editable_resources": True,
            "user_editable_organizations": True,
        },
    )
    organization, _ = Organization.objects.get_or_create(
        id=settings.EXTERNAL_USER_PUBLISHER_ID,
        defaults={"name": "Muu", "data_source": data_source},
    )
    return organization


def organization_can_be_edited_by(organization: Organization, user):
    return user.is_superuser or organization in user.admin_organizations.all()


def get_user_data_source_and_organization_from_request(
    request,
) -> tuple[DataSource, Organization]:
    """Get the data source and organization for the user from the request.

    :param request: the request object
    :return: a tuple containing the data source and organization
    """

    # api_key takes precedence over user
    if isinstance(request.auth, ApiKeyAuth):
        data_source = request.auth.get_authenticated_data_source()
        publisher = data_source.owner
        if not publisher:
            raise PermissionDenied(_("Data source doesn't belong to any organization"))
    else:
        # objects *created* by api are marked coming from the system data source unless api_key is provided  # noqa: E501
        # we must optionally create the system data source here, as the settings
        # may have changed at any time
        system_data_source_defaults = {
            "user_editable_resources": True,
            "user_editable_organizations": True,
        }
        data_source, created = DataSource.objects.get_or_create(
            id=settings.SYSTEM_DATA_SOURCE_ID, defaults=system_data_source_defaults
        )
        # user organization is used unless api_key is provided
        user = request.user
        if isinstance(user, User):
            publisher = user.get_default_organization()
        else:
            publisher = None
        # no sense in doing the replacement check later, the authenticated
        # publisher must be current to begin with
        if publisher and publisher.replaced_by:
            publisher = publisher.replaced_by
    return data_source, publisher


def clean_text_fields(
    data,
    allowed_html_fields: Optional[Iterable[str]] = None,
    strip: bool = False,
):
    if allowed_html_fields is None:
        allowed_html_fields = []

    for k, v in data.items():
        if isinstance(v, str) and any(c in v for c in "<>&"):
            # only specified fields may contain allowed tags
            for field_name in allowed_html_fields:
                # check all languages and the default translation field too
                if k.startswith(field_name):
                    data[k] = bleach.clean(v, settings.BLEACH_ALLOWED_TAGS, strip=strip)
                    break
            else:
                data[k] = bleach.clean(v, [], strip=strip)
                # for non-html data, ampersands should be bare
                data[k] = data[k].replace("&amp;", "&")
    return data
