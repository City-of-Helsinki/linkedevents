import logging
import re
from collections.abc import Generator
from functools import lru_cache
from operator import itemgetter

import libvoikko
from django.conf import settings
from django.db.models import QuerySet
from num2words import num2words

from events.importer.utils import clean_text

logger = logging.getLogger(__name__)

# setup libvoikko
voikko = libvoikko.Voikko("fi", "/etc/voikko")
voikko.setNoUglyHyphenation(True)

stop_word_classes = set(settings.VOIKKO_FINNISH_STOPWORD_CLASSES)
check_stop_words = len(stop_word_classes) > 0


def get_field_attr(obj: object, field: str) -> str:
    """
    Get attr recursively by following foreign key relations.
    :param obj: object to get the attribute from
    :param field: field name or foreign key relation
    :return: attribute value
    """
    fields = field.split("__")
    if len(fields) == 1:
        return getattr(obj, fields[0], None)
    else:
        first_field = fields[0]
        remaining_fields = "__".join(fields[1:])
        return get_field_attr(getattr(obj, first_field), remaining_fields)


_structure_item_getter = itemgetter("STRUCTURE")


def analyze_word(word: str) -> list:
    results = voikko.analyze(word)
    # Voikko appears to not return the results in a stable manner
    # across different systems so we sort the results to avoid
    # flaky tests
    if len(results) > 1:
        results.sort(key=_structure_item_getter)
    return results


@lru_cache(maxsize=settings.FULL_TEXT_WORDS_CACHE_SIZE)
def get_word_bases(word: str) -> list:
    """
    Returns a list of word bases of the word.
    :param word: the word to split
    :return: a list of word bases
    """
    words = []
    word = word.strip()
    analysis = analyze_word(word)
    if len(analysis) == 0:
        # if the word can't be analyzed, return the word itself
        words.append(word)
        return words
    for item in analysis:
        if check_stop_words and "CLASS" in item and item["CLASS"] in stop_word_classes:
            # if the word is a stop word, skip it
            continue
        # extract the bases from the string
        if "WORDBASES" in item:
            word_bases = re.findall(r"\(([^+].*?)\)", item["WORDBASES"])
            for base in word_bases:
                # remove non-word characters
                base = re.sub(r"\W", "", base)
                words.append(base)
        else:
            words.append(word)
    return words


def extract_word_bases(text: str, words: list, lang: str = "fi") -> list:
    """
    Splits the word into its bases and adds them to the list of words.
    :param text: the text to split
    :param words: the list of words to add the bases to
    :param lang: the language of the word (default: "fi")
    :return: a list of extracted words
    """
    # remove html tags and newlines
    cleaned_text = clean_text(
        text or "", strip_newlines=True, parse_html=True, separator=" "
    )
    # replace non-word characters with space
    cleaned_text = re.sub(r"\W", " ", cleaned_text)
    cleaned_words = cleaned_text.split() if cleaned_text else []
    for word in cleaned_words:
        # convert numbers to words
        numbers = convert_numbers(word, lang=lang)
        if numbers:
            words.extend(numbers)
        # if the word is in Finnish, get its bases
        word_bases = get_word_bases(word) if lang == "fi" else [word]
        if word_bases:
            words.extend(word_bases)
    return words


def convert_numbers(word: str, lang: str = "fi") -> list:
    """
    Converts numbers in the word to textual words.
    :param word: the word to process
    :param lang: the language to convert to (default: "fi")
    :return: a list of converted words
    """
    words = []
    numbers = re.sub(r"\D+", " ", word).split()
    if numbers:
        # add numbers itself also
        words.extend(numbers)
    for number in numbers:
        # convert the number to language-specific words
        try:
            num = num2words(number, lang=lang)
            if num:
                words.append(num)
        except NotImplementedError:
            pass
    return words


def batch_qs(qs: QuerySet, batch_size: int = 1000) -> Generator:
    """
    Returns a (start, end, total, queryset) tuple for each batch in the given
    queryset. Make sure to order the queryset before calling this function.
    :param qs: the queryset to batch
    :param batch_size: the size of each batch (default: 1000)
    :return: a generator that yields (start, end, total, queryset) tuples
    """
    total = qs.count()
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        yield start, end, total, qs[start:end]
