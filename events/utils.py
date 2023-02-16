import collections
import re
import warnings
from datetime import datetime, timedelta
from typing import Optional

import pytz
from dateutil.parser import parse as dateutil_parse
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django_orghierarchy.models import Organization
from rest_framework.exceptions import ParseError

from events.models import DataSource, Keyword, Place
from events.sql import count_events_for_keywords, count_events_for_places


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


def parse_time(time_str, is_start):
    local_tz = pytz.timezone(settings.TIME_ZONE)
    time_str = time_str.strip()
    is_exact = True
    # Handle dates first. Assume dates are given in local timezone.
    # FIXME: What if there's no local timezone?
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d")
        dt = local_tz.localize(dt)
        is_exact = False
    except ValueError:
        dt = None
    if not dt:
        if time_str.lower() == "today":
            # DST safe
            dt = timezone.now().astimezone(local_tz).replace(tzinfo=None)
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            dt = local_tz.localize(dt)

            is_exact = False
        if time_str.lower() == "now":
            dt = timezone.now()
            is_exact = True
    if dt and not is_exact:
        # With start timestamps, we treat dates as beginning
        # at midnight the same day. End timestamps are taken to
        # mean midnight on the following day.
        if not is_start:
            # DST safe
            naive_datetime = dt.astimezone(local_tz).replace(tzinfo=None)
            naive_datetime += timedelta(days=1)
            dt = local_tz.localize(naive_datetime)
    elif not dt:
        try:
            # Handle all other times through dateutil.
            dt = dateutil_parse(time_str)
            # Dateutil may allow dates with too large negative tzoffset, crashing psycopg later
            if dt.tzinfo and abs(dt.tzinfo.utcoffset(dt)) > timedelta(hours=15):
                raise ParseError(f"Time zone given in timestamp {dt} out of bounds.")
            # Datetimes without timezone are assumed UTC by drf
        except (TypeError, ValueError, OverflowError):
            raise ParseError("time in invalid format (try ISO 8601 or yyyy-mm-dd)")
    # if not dt.tzinfo:
    #     dt = dt.astimezone(pytz.timezone('UTC'))
    return dt, is_exact


def get_fixed_lang_codes():
    lang_codes = []
    for language in settings.LANGUAGES:
        lang_code = language[0]
        lang_code = lang_code.replace(
            "-", "_"
        )  # to handle complex codes like e.g. zh-hans
        lang_codes.append(lang_code)
    return lang_codes


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
    if not settings.USER_DEFAULT_ORGANIZATION_ID:
        warnings.warn(
            "USER_DEFAULT_ORGANIZATION_ID is empty, will not set or create "
            "default organization."
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
        id=settings.USER_DEFAULT_ORGANIZATION_ID,
        defaults={"name": "Muu", "data_source": data_source},
    )
    return organization
