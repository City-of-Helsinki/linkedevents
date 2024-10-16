import re
import string

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, TrigramSimilarity
from rest_framework.exceptions import ParseError

from events.models import KeywordLabel


class KeywordMatcher(object):
    def __init__(self):
        pass

    def full_text_matching(self, text, language=None):
        used_langs = settings.FULLTEXT_SEARCH_LANGUAGES
        if language:
            if language not in used_langs.keys():
                raise ParseError(
                    f"{language} not supported. Supported options are: {' '.join(used_langs.keys())}"  # noqa: E501
                )
            languages = [language]
        else:
            languages = used_langs.keys()

        contestants = {}
        for language in languages:
            query = SearchQuery(text, config=used_langs[language], search_type="plain")
            kwargs = {f"search_vector_{language}": query}

            # find matches via search vector and choose the best one according to
            # trgrm similarity
            label = (
                KeywordLabel.objects.filter(**kwargs)
                .annotate(similarity=TrigramSimilarity("name", text))
                .order_by("-similarity")  # noqa E124
                .first()
            )  # noqa E124
            # storing the result in a dictionary of the following structure {similarity: label}  # noqa: E501
            # in the edge case when similarity is the same for two different languages the label will be  # noqa: E501
            # overwritten, which is not big deal as we don't have a way to select
            # between the two anyway.
            if label:
                contestants[label.similarity] = label

        # selecting the match with the highest similarity, if there is anything to
        # select
        if contestants.keys():
            return contestants[max(contestants.keys())]
        else:
            return None

    def label_match(self, text, language=None):
        # Let's use Postgres full-text search to find a label matched by lexeme and rank the results with  # noqa: E501
        # TrigramSimilarity as fulltext SearchRank is not suitable for ranking matched individual words. If no language  # noqa: E501
        # is passed we cycle through all options as specified in FULLTEXT_SEARCH_LANGUAGES and select the best match  # noqa: E501
        # according to similarity.
        label = self.full_text_matching(text, language)
        if label:
            return [label]

        # if no matches found let's check if we could split the string
        texts = re.split(f"[{string.punctuation} ]", text)
        if len(texts) > 1:
            all_the_labels = []
            for word in texts:
                label = self.label_match(word, language)
                if label:
                    all_the_labels.extend(label)
            return all_the_labels if all_the_labels else None
        else:
            return None

    def match(self, text, language=None):
        labels = self.label_match(text, language)
        keywords = []
        if labels:
            for label in labels:
                keywords.extend(label.keywords.filter(deprecated=False))
            return keywords
        else:
            return None
