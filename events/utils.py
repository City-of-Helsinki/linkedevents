import collections
import re
from datetime import datetime, timedelta

import pytz
from dateutil.parser import parse as dateutil_parse
from django.conf import settings
from django.db import models, transaction
from haystack import signals
from haystack.exceptions import NotHandled
from rest_framework.exceptions import ParseError

from events.models import Keyword, Place
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
            dt = datetime.utcnow().replace(tzinfo=pytz.utc)
            dt = dt.astimezone(local_tz)
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            is_exact = False
        if time_str.lower() == "now":
            dt = datetime.utcnow().replace(tzinfo=pytz.utc)
            is_exact = True
    if dt and not is_exact:
        # With start timestamps, we treat dates as beginning
        # at midnight the same day. End timestamps are taken to
        # mean midnight on the following day.
        if not is_start:
            dt = dt + timedelta(days=1)
    elif not dt:
        try:
            # Handle all other times through dateutil.
            dt = dateutil_parse(time_str)
            # Dateutil may allow dates with too large negative tzoffset, crashing psycopg later
            if dt.tzinfo and abs(dt.tzinfo.utcoffset(dt)) > timedelta(hours=15):
                raise ParseError(f"Time zone given in timestamp {dt} out of bounds.")
            # Datetimes without timezone are assumed UTC by drf
        except (TypeError, ValueError):
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


class QueuedUpdateSignalProcessor(signals.BaseSignalProcessor):
    save_queue = None

    def setup(self):
        models.signals.post_save.connect(self.enqueue_save)
        models.signals.post_delete.connect(self.handle_delete)
        self.save_queue = collections.defaultdict(lambda: [])

    def teardown(self):
        models.signals.post_save.disconnect(self.enqueue_save)
        models.signals.post_delete.disconnect(self.handle_delete)

    def enqueue_save(self, sender, instance, **kwargs):
        self.save_queue[sender].append(instance)

    def flush(self):
        sender_map = {}
        backend_map = {}
        instance_map = collections.defaultdict(lambda: [])
        for sender, instances in self.save_queue.items():
            if sender not in sender_map:
                sender_map[sender] = sender

            for instance in instances:
                using_backends = self.connection_router.for_write(instance=instance)
                for using_backend in using_backends:
                    if using_backend not in backend_map:
                        backend_map[using_backend] = using_backend
                    instance_map[(sender, using_backend)].append(instance)

        for (str_sender, str_using_backend), instances in instance_map.items():
            sender = sender_map[str_sender]
            using_backend = backend_map[str_using_backend]
            engine = self.connections[using_backend]
            try:
                index = engine.get_unified_index().get_index(sender)
            except NotHandled:
                # We receive naively signals from all models, including those
                # that are not registered to the index.
                # These will raise NotHandled and can be safely ignored as
                # irrelevant noise.
                continue
            engine.get_backend().update(index, instances)

        self.save_queue.clear()
