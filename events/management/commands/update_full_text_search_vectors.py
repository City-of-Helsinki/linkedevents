import logging

from django.contrib.postgres.search import SearchVector
from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery

from events.models import Event, EventSearchIndex
from events.utils import get_field_attr, split_word_bases

logger = logging.getLogger(__name__)


def update_full_text_search_vectors():
    """
    Updates the full text search objects for the events.
    This function iterates through all events, extracts words from the specified
    columns, and updates the EventSearchIndex model with the search vectors.
    :param lang: The language code for the search objects (default is "fi").
    :return: The number of populated search objects.
    """
    num_populated = 0
    qs = Event.objects.all().order_by("pk")[:100]
    for event in qs.iterator(chunk_size=10000):
        words_fi = set()
        for column in Event.get_words_fi_columns():
            row_content = get_field_attr(event, column)
            if row_content:
                # Rows might be of type str or Array, if str
                # cast to array by splitting.
                if isinstance(row_content, str):
                    row_content = row_content.split()
                for word in row_content:
                    word_bases = get_word_bases(word)
                    if len(word_bases) > 1:
                        for w in word_bases:
                            words_fi.add(w)

        logger.info(f"Updating search vectors for {event.id}, words: {words_fi}")

        # create or update EventSearchIndex object
        EventSearchIndex.objects.update_or_create(
            event=event,
            defaults={
                "place": event.location,
                "event_last_modified_time": event.last_modified_time,
                "place_last_modified_time": event.location.last_modified_time,
                "words_fi": list(words_fi),
            },
        )
        num_populated += 1


def update_full_text_search_vectors():
    """
    Updates the search vectors for the full text search objects.
    """
    eqs = Event.objects.filter(full_text=OuterRef("pk"))
    EventSearchIndex.objects.all().annotate(
        event_name_fi=Subquery(eqs.values("name_fi")[:1]),
        event_description_fi=Subquery(eqs.values("description_fi")[:1]),
        event_short_description_fi=Subquery(eqs.values("short_description_fi")[:1]),
        place_name=Subquery(eqs.values("location__name_fi")[:1]),
    ).update(
        search_vector_fi=SearchVector("event_name", config="finnish", weight="A")
        + SearchVector("event_description", config="finnish", weight="D")
        + SearchVector("event_short_description_fi", config="finnish", weight="C")
        + SearchVector("place_name", config="finnish", weight="A")
        + SearchVector("words_fi", config="finnish", weight="A")
    )

    return num_populated


class Command(BaseCommand):
    def handle(self, *args, **options):
        for lang in ["fi", "sv", "en"]:
            # TODO: Only finnish language for now
            if lang == "fi":
                logger.info(f"Generating search vectors for language: {lang}.")
                num_populated = update_full_text_search_vectors()
                logger.info(f"Search vectors updated for {num_populated} Events")
