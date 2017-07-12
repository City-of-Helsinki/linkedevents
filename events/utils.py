from datetime import datetime, timedelta
import re
import collections

import pytz
from django.db import transaction
from django.conf import settings
from dateutil.parser import parse as dateutil_parse
from rest_framework.exceptions import ParseError

from events.models import Keyword, Place
from events.sql import count_events_for_keywords, count_events_for_places


def convert_to_camelcase(s):
    return ''.join(word.title() if i else word for i, word in enumerate(
        s.split('_')))


def convert_from_camelcase(s):
    return re.sub(r'(^|[a-z])([A-Z])',
                  lambda m: '_'.join([i.lower() for i in m.groups() if i]), s)


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
    for i, v in enumerate(list_of_tuples):
        if v[value_index ^ 1] == search_key:
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
            Keyword.objects.filter(id__in=keyword_ids).update(n_events=0)
        for keyword_id, n_events in count_events_for_keywords(keyword_ids, all=all).items():
            Keyword.objects.filter(id=keyword_id).update(n_events=n_events, n_events_changed=False)


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
            Place.objects.filter(id__in=place_ids).update(n_events=0)
        for place_id, n_events in count_events_for_places(place_ids, all=all).items():
            Place.objects.filter(id=place_id).update(n_events=n_events, n_events_changed=False)


def parse_time(time_str, is_start):
    local_tz = pytz.timezone(settings.TIME_ZONE)
    time_str = time_str.strip()
    # Handle dates first. Assume dates are given in local timezone.
    # FIXME: What if there's no local timezone?
    try:
        dt = datetime.strptime(time_str, '%Y-%m-%d')
        dt = local_tz.localize(dt)
    except ValueError:
        dt = None
    if not dt:
        if time_str.lower() == 'today':
            dt = datetime.utcnow().replace(tzinfo=pytz.utc)
            dt = dt.astimezone(local_tz)
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if dt:
        # With start timestamps, we treat dates as beginning
        # at midnight the same day. End timestamps are taken to
        # mean midnight on the following day.
        if not is_start:
            dt = dt + timedelta(days=1)
    else:
        try:
            # Handle all other times through dateutil.
            dt = dateutil_parse(time_str)
        except (TypeError, ValueError):
            raise ParseError('time in invalid format (try ISO 8601 or yyyy-mm-dd)')
    return dt
