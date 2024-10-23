from django.db import connection


def count_events_for_keywords(keyword_ids=(), all=False):
    """
    Get the actual count of events using the given keywords.

    :param keyword_ids: set of keyword ids
    :type keyword_ids: Iterable[str]
    :param all: count all keywords instead
    :type all: bool
    :return: dict of keyword id to count
    :rtype: dict[str, int]
    """
    # sorry for the non-DRY-ness; would be easier with an SQL generator like
    # SQLAlchemy, but...

    keyword_ids = tuple(set(keyword_ids))
    with connection.cursor() as cursor:
        if keyword_ids:
            cursor.execute(
                """
            SELECT t.keyword_id, COUNT(DISTINCT t.event_id)
            FROM (
              SELECT keyword_id, event_id FROM events_event_keywords WHERE keyword_id IN %s
              UNION
              SELECT keyword_id, event_id FROM events_event_audience WHERE keyword_id IN %s
            ) t
            GROUP BY t.keyword_id;
            """,  # noqa: E501
                [keyword_ids, keyword_ids],
            )
        elif all:
            cursor.execute(
                """
            SELECT t.keyword_id, COUNT(DISTINCT t.event_id)
            FROM (
              SELECT keyword_id, event_id FROM events_event_keywords
              UNION
              SELECT keyword_id, event_id FROM events_event_audience
            ) t
            GROUP BY t.keyword_id;
            """
            )
        else:
            return {}
        return dict(cursor.fetchall())


def count_events_for_places(place_ids=(), all=False):
    """
    Get the actual count of events in the given places.

    :param place_ids: set of place ids
    :type place_ids: Iterable[str]
    :param all: count all places instead
    :type all: bool
    :return: dict of place id to count
    :rtype: dict[str, int]
    """
    # sorry for the non-DRY-ness; would be easier with an SQL generator like
    # SQLAlchemy, but...

    place_ids = tuple(set(place_ids))
    with connection.cursor() as cursor:
        if place_ids:
            cursor.execute(
                """
            SELECT e.location_id, COUNT(*)
            FROM events_event e
            WHERE location_id IN %s
            GROUP BY e.location_id;
            """,
                [place_ids],
            )
        elif all:
            cursor.execute(
                """
            SELECT e.location_id, COUNT(*)
            FROM events_event e
            GROUP BY e.location_id;
            """
            )
        else:
            return {}
        return dict(cursor.fetchall())
