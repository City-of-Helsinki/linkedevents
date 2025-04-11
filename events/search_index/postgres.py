import logging
from typing import Optional

from django.contrib.postgres.search import SearchVector
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from events.models import Event, EventSearchIndex
from events.search_index.utils import get_field_attr, split_word_bases

logger = logging.getLogger(__name__)


class EventSearchIndexService:
    """
    Service class for managing the event search index.
    """

    @classmethod
    def get_words(cls, event: Event, lang: str) -> set:
        words = set()
        for column in Event.get_words_columns(lang):
            row_content = get_field_attr(event, column)
            if row_content:
                split_word_bases(row_content, words, lang)

        for keyword in event.keywords.values_list("name_%s" % lang, flat=True):
            split_word_bases(keyword, words, lang)

        logger.debug(
            f"Getting words for event: {event.id}, lang: {lang}, words: {words}"
        )
        return words

    @classmethod
    def update_search_index(cls, event: Event) -> None:
        """
        Update the search index for a given event.
        """
        if event:
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
                    "words_fi": list(cls.get_words(event, "fi")),
                    "words_sv": list(cls.get_words(event, "sv")),
                    "words_en": list(cls.get_words(event, "en")),
                },
            )
            logger.info(f"Updated search index for event: {event.id}")

    @classmethod
    def bulk_update_search_indexes(cls) -> int:
        """
        Bulk update the search index for events.
        Create a new EventSearchIndex object for each event
        and saves it to the database.
        Use bulk_create to improve performance.
        """

        num_updated = 0
        event_index_objects = []

        qs = (
            Event.objects.all()
            .select_related("location")
            .prefetch_related("keywords")
            .order_by("pk")
        )

        for event in qs.iterator(chunk_size=10000):
            event_index = EventSearchIndex(
                event=event,
                place=event.location if event else None,
                event_last_modified_time=event.last_modified_time
                if event
                else timezone.now(),
                place_last_modified_time=event.location.last_modified_time
                if event and event.location
                else timezone.now(),
                words_fi=list(cls.get_words(event, "fi")),
                words_sv=list(cls.get_words(event, "sv")),
                words_en=list(cls.get_words(event, "en")),
            )
            event_index_objects.append(event_index)
            num_updated += 1
        EventSearchIndex.objects.bulk_create(
            event_index_objects,
            update_conflicts=True,
            unique_fields=["event"],
            update_fields=[
                "place",
                "event_last_modified_time",
                "place_last_modified_time",
                "words_fi",
                "words_sv",
                "words_en",
            ],
        )
        return num_updated

    @classmethod
    def update_index_search_vectors(cls, event: Optional[Event] = None) -> None:
        """
        Update search vectors for the search index.

        If event is given, only update that event's search vectors.
        Otherwise, update all events' search vectors.
        """
        if event:
            qs = EventSearchIndex.objects.filter(event=event)
        else:
            qs = EventSearchIndex.objects.all()

        eqs = Event.objects.filter(full_text=OuterRef("pk"))
        qs.annotate(
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
            search_vector_fi=SearchVector("event_name_fi", config="simple", weight="A")
            + SearchVector("place_name_fi", config="simple", weight="A")
            + SearchVector("words_fi", config="simple", weight="A")
            + SearchVector("keywords_fi", config="simple", weight="B")
            + SearchVector("event_short_description_fi", config="simple", weight="C")
            + SearchVector("event_description_fi", config="simple", weight="D"),
            search_vector_sv=SearchVector("event_name_sv", config="simple", weight="A")
            + SearchVector("place_name_sv", config="simple", weight="A")
            + SearchVector("words_sv", config="simple", weight="A")
            + SearchVector("keywords_sv", config="simple", weight="B")
            + SearchVector("event_short_description_sv", config="simple", weight="C")
            + SearchVector("event_description_sv", config="simple", weight="D"),
            search_vector_en=SearchVector("event_name_en", config="simple", weight="A")
            + SearchVector("place_name_en", config="simple", weight="A")
            + SearchVector("words_en", config="simple", weight="A")
            + SearchVector("keywords_en", config="simple", weight="B")
            + SearchVector("event_short_description_en", config="simple", weight="C")
            + SearchVector("event_description_en", config="simple", weight="D"),
        )
