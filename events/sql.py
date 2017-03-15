from django.db import connection


def count_events_for_keywords(keyword_ids=()):
    """
    Get the actual count of events using the given keywords.

    :param keyword_ids: set of keyword ids; pass an empty set to get the data for all keywords
    :type keyword_ids: Iterable[str]
    :return: dict of keyword id to count
    :rtype: dict[str, int]
    """
    # sorry for the non-DRY-ness; would be easier with an SQL generator like SQLAlchemy, but...

    keyword_ids = tuple(set(keyword_ids))
    with connection.cursor() as cursor:
        if keyword_ids:
            cursor.execute('''
            SELECT t.keyword_id, COUNT(DISTINCT t.event_id)
            FROM (
              SELECT keyword_id, event_id FROM events_event_keywords WHERE keyword_id IN %s
              UNION
              SELECT keyword_id, event_id FROM events_event_audience WHERE keyword_id IN %s
            ) t
            GROUP BY t.keyword_id;
            ''', [keyword_ids, keyword_ids])
        else:
            cursor.execute('''
            SELECT t.keyword_id, COUNT(DISTINCT t.event_id)
            FROM (
              SELECT keyword_id, event_id FROM events_event_keywords
              UNION
              SELECT keyword_id, event_id FROM events_event_audience
            ) t
            GROUP BY t.keyword_id;
            ''')
        return dict(cursor.fetchall())
