import logging
from typing import Optional

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.postgres.search import SearchVector
from django.db.models import Q
from django.utils import timezone

from events.models import Event, EventSearchIndex
from events.search_index.utils import batch_qs, extract_word_bases, get_field_attr
from linkedevents.utils import get_fixed_lang_codes

logger = logging.getLogger(__name__)

languages = get_fixed_lang_codes()


class EventSearchIndexService:
    """
    Service class for managing the event search index.
    """

    @classmethod
    def get_words(cls, event: Event, lang: str, weight: str = "A") -> set:
        words = set()
        for column in Event.get_words_fields(lang, weight):
            row_content = get_field_attr(event, column)
            if row_content:
                extract_word_bases(row_content, words, lang)

        if weight == "B":
            for keyword in event.keywords.values_list("name_%s" % lang, flat=True):
                extract_word_bases(keyword, words, lang)

            for keyword in event.audience.values_list("name_%s" % lang, flat=True):
                extract_word_bases(keyword, words, lang)

        return words

    @classmethod
    def get_weighted_words(cls, event: Event) -> dict:
        """
        Get the words and their weights for a given event.
        """
        weighted_words = {}
        for lang in languages:
            weighted_words.update(
                {
                    f"words_{lang}_weight_a": list(cls.get_words(event, lang, "A")),
                    f"words_{lang}_weight_b": list(cls.get_words(event, lang, "B")),
                    f"words_{lang}_weight_c": list(cls.get_words(event, lang, "C")),
                    f"words_{lang}_weight_d": list(cls.get_words(event, lang, "D")),
                }
            )
        return weighted_words

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
                    **cls.get_weighted_words(event),
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
        logger.info("Updating search indexes...")
        # only include events that are less than rebuild time limit
        # or those without end_time
        event_qs = (
            Event.objects.filter(
                Q(
                    end_time__gte=timezone.now()
                    - relativedelta(
                        months=settings.EVENT_SEARCH_INDEX_REBUILD_END_TIME_MAX_AGE_MONTHS
                    )
                )
                | Q(end_time=None)
            )
            .select_related("location")
            .prefetch_related("keywords", "audience")
            .order_by("pk")
        )

        # pre-generate language-specific words update fields
        words_fields = (
            [f"words_{lang}_weight_a" for lang in languages]
            + [f"words_{lang}_weight_b" for lang in languages]
            + [f"words_{lang}_weight_c" for lang in languages]
            + [f"words_{lang}_weight_d" for lang in languages]
        )

        for start, end, total, qs in batch_qs(
            event_qs, batch_size=settings.EVENT_SEARCH_INDEX_REBUILD_BATCH_SIZE
        ):
            logger.info(f"Now processing {start + 1} - {end} of {total}")
            event_index_objects = []
            for event in qs:
                event_index = EventSearchIndex(
                    event=event,
                    place=event.location if event else None,
                    event_last_modified_time=event.last_modified_time
                    if event
                    else timezone.now(),
                    place_last_modified_time=event.location.last_modified_time
                    if event and event.location
                    else timezone.now(),
                    **cls.get_weighted_words(event),
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
                    *words_fields,
                ],
            )
        logger.info(f"Search index updated for {num_updated} Events")
        return num_updated

    @classmethod
    def update_index_search_vectors(cls, event: Optional[Event] = None) -> None:
        """
        Update search vectors for the search index.

        If event is given, only update that event's search vectors.
        Otherwise, update all events' search vectors.
        """
        logger.info("Updating search vectors...")
        if event:
            qs = EventSearchIndex.objects.filter(event=event)
        else:
            qs = EventSearchIndex.objects.all()

        qs.update(
            **{
                f"search_vector_{lang}": SearchVector(
                    f"words_{lang}_weight_a", config="simple", weight="A"
                )
                + SearchVector(f"words_{lang}_weight_b", config="simple", weight="B")
                + SearchVector(f"words_{lang}_weight_c", config="simple", weight="C")
                + SearchVector(f"words_{lang}_weight_d", config="simple", weight="D")
                for lang in languages
            },
        )
        logger.info("Search vectors updated.")
