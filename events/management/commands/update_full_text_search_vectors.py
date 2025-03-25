import logging

from django.contrib.postgres.search import SearchVector
from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from events.models import Event, EventSearchIndex
from events.utils import get_field_attr, split_word_bases

logger = logging.getLogger(__name__)


def update_full_text_search_objects(lang: str = "fi") -> int:
    """
    Updates the full text search objects for the events.
    This function iterates through all events, extracts words from the specified
    columns, and updates the EventSearchIndex model with the search vectors.
    :param lang: The language code for the search objects (default is "fi").
    :return: The number of populated search objects.
    """
    num_populated = 0
    qs = Event.objects.all().order_by("pk")
    for event in qs.iterator(chunk_size=10000):
        words = set()
        for column in Event.get_words_columns(lang):
            row_content = get_field_attr(event, column)
            if row_content:
                split_word_bases(row_content, words, lang)

        for keyword in event.keywords.values_list("name_%s" % lang, flat=True):
            split_word_bases(keyword, words, lang)

        logger.debug(f"Updating search vectors for {event.id}, words: {words}")

        # create or update EventSearchIndex object
        EventSearchIndex.objects.update_or_create(
            event=event,
            defaults={
                "place": event.location if event else None,
                "event_last_modified_time": event.last_modified_time
                if event
                else timezone.now(),
                "place_last_modified_time": event.location.last_modified_time
                if event and event.location
                else timezone.now(),
                "words_%s" % lang: list(words),
            },
        )
        num_populated += 1
    return num_populated


def update_full_text_search_vectors():
    """
    Updates the search vectors for the full text search objects.
    """
    eqs = Event.objects.filter(full_text=OuterRef("pk"))
    EventSearchIndex.objects.all().annotate(
        event_name_fi=Subquery(eqs.values("name_fi")[:1]),
        event_description_fi=Subquery(eqs.values("description_fi")[:1]),
        event_short_description_fi=Subquery(eqs.values("short_description_fi")[:1]),
        place_name_fi=Subquery(eqs.values("location__name_fi")[:1]),
        event_name_sv=Subquery(eqs.values("name_sv")[:1]),
        event_description_sv=Subquery(eqs.values("description_sv")[:1]),
        event_short_description_sv=Subquery(eqs.values("short_description_sv")[:1]),
        place_name_sv=Subquery(eqs.values("location__name_sv")[:1]),
        event_name_en=Subquery(eqs.values("name_en")[:1]),
        event_description_en=Subquery(eqs.values("description_en")[:1]),
        event_short_description_en=Subquery(eqs.values("short_description_en")[:1]),
        place_name_en=Subquery(eqs.values("location__name_en")[:1]),
        keywords_fi=Subquery(eqs.values("keywords__name_fi")[:1]),
        keywords_sv=Subquery(eqs.values("keywords__name_sv")[:1]),
        keywords_en=Subquery(eqs.values("keywords__name_en")[:1]),
    ).update(
        search_vector_fi=SearchVector("event_name_fi", config="finnish", weight="A")
        + SearchVector("place_name_fi", config="finnish", weight="A")
        + SearchVector("words_fi", config="finnish", weight="A")
        + SearchVector("keywords_fi", config="finnish", weight="B")
        + SearchVector("event_short_description_fi", config="finnish", weight="C")
        + SearchVector("event_description_fi", config="finnish", weight="D"),
        search_vector_sv=SearchVector("event_name_sv", config="swedish", weight="A")
        + SearchVector("place_name_sv", config="swedish", weight="A")
        + SearchVector("words_sv", config="swedish", weight="A")
        + SearchVector("keywords_sv", config="swedish", weight="B")
        + SearchVector("event_short_description_sv", config="swedish", weight="C")
        + SearchVector("event_description_sv", config="swedish", weight="D"),
        search_vector_en=SearchVector("event_name_en", config="english", weight="A")
        + SearchVector("place_name_en", config="english", weight="A")
        + SearchVector("words_en", config="english", weight="A")
        + SearchVector("keywords_en", config="english", weight="B")
        + SearchVector("event_short_description_en", config="english", weight="C")
        + SearchVector("event_description_en", config="english", weight="D"),
    )


class Command(BaseCommand):
    def handle(self, *args, **options):
        for lang in ["fi", "sv", "en"]:
            logger.info(f"Generating search vectors for language: {lang}.")
            num_populated = update_full_text_search_objects(lang)
            logger.info(f"Search vectors updated for {num_populated} Events")
        update_full_text_search_vectors()
