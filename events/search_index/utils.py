import logging
import re
from functools import cache
from typing import Generator

import libvoikko
from django.db.models import QuerySet

from events.importer.utils import clean_text

logger = logging.getLogger(__name__)

# setup libvoikko
voikko = libvoikko.Voikko("fi", "/etc/voikko")
voikko.setNoUglyHyphenation(True)


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


@cache
def analyze_word(word: str) -> list:
    return voikko.analyze(word)


def get_word_bases(word: str) -> set:
    """
    Returns a list of word bases of the word.
    :param word: the word to split
    :return: a list of word bases
    """
    words = set()
    word = word.strip()
    analysis = analyze_word(word)
    if len(analysis) == 0:
        # if the word can't be analyzed, return the word itself
        words.add(word)
        return words
    for item in analysis:
        # extract the bases from the string
        if "WORDBASES" in item:
            word_bases = re.findall(r"\(([^+].*?)\)", item["WORDBASES"])
            words.update(word_bases)
        else:
            words.add(word)
    return words


def split_word_bases(word: str, words: set, lang: str = "fi") -> set:
    """
    Splits the word into its bases and adds them to the set of words.
    :param word: the word to split
    :param words: the set of words to add the bases to
    :param lang: the language of the word (default: "fi")
    :return: the set of words
    """
    # replace common separators with spaces
    word = re.sub(r"[;:,.?!-]", " ", word or "")
    # remove html tags and newlines
    word = clean_text(word, strip_newlines=True, parse_html=True)
    if lang == "fi":
        w_array = word or []
        if isinstance(word, str):
            w_array = word.split()
        for word in w_array:
            word_bases = get_word_bases(word)
            words.update(word_bases)
    else:
        # for other languages, just add the word itself
        words.add(word)
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
