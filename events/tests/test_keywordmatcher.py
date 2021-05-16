import pytest
from django.contrib.postgres.search import SearchQuery

from events.keywords import KeywordMatcher
from events.models import KeywordLabel, Language


@pytest.mark.django_db
def test_keyword_label_trigger(languages):
    ''' Triggers were added in Postgres to update search vectors each time a KeywordLabel in matching language is
        added, removed, or modified'''

    query = SearchQuery('ducks', config='english',)
    assert KeywordLabel.objects.filter(search_vector_en=query).count() == 0
    assert KeywordLabel.objects.filter(search_vector_en=query).count() == 0

    KeywordLabel(language=Language.objects.get(id='en'), name='duck').save()
    #  Trigger should now update the search vector for English, but not for Finnish
    assert KeywordLabel.objects.filter(search_vector_en=query).count() == 1
    assert KeywordLabel.objects.filter(search_vector_fi=query).count() == 0

    #  search vector is updated on KeywordLabel update
    KeywordLabel.objects.filter(name='duck').update(name='Donald')
    assert KeywordLabel.objects.filter(search_vector_en=query).count() == 0
    KeywordLabel.objects.filter(name='Donald').update(name='duck')
    assert KeywordLabel.objects.filter(search_vector_en=query).count() == 1
    assert KeywordLabel.objects.filter(search_vector_fi=query).count() == 0

    #  and on delete
    KeywordLabel.objects.get(name='duck').delete()
    assert KeywordLabel.objects.filter(search_vector_en=query).count() == 0


#  KeywordMatcher takes as input the strings of words with or without language specification and transforms them
#  into a list of Keywords. Postgres full-text search is used to find a label matched by lexeme. The results are ranked
#  with TrigramSimilarity as full-text SearchRank is not suitable for ranking individual words. If no language is
#  passed we cycle through all options as specified in FULLTEXT_SEARCH_LANGUAGES and select the best match according
#  to similarity. If no match is found the string is checked for the possibility that it could be split and search for
#  matches is repeated.
#  Syntactic dust - punctuation marks etc. - is ignored.
#  If the language is specified the search is conducted only within the language specific search vectors.
@pytest.mark.django_db
def test_keyword_match(languages, data_source, organization, keyword, keyword2):
    kl = KeywordLabel(language=Language.objects.get(id='fi'), name='lapsi')
    kl.save()
    kl2 = KeywordLabel(language=Language.objects.get(id='fi'), name='teatteri')
    kl2.save()
    keyword.alt_labels.add(kl)
    keyword2.alt_labels.add(kl2)

    matcher = KeywordMatcher()
    assert set([keyword, keyword2]) == set(matcher.match('[lapsi! teatteriin}'))
    assert set([keyword, keyword2]) == set(matcher.match('[lapsi! teatteriin}', language='fi'))
    assert matcher.match('[lapsi! teatteriin}', language='en') is None


@pytest.mark.django_db
def test_keyword_match_trgrm(languages, data_source, organization, keyword, keyword2):
    kl = KeywordLabel(language=Language.objects.get(id='fi'), name='asdfg')
    kl.save()
    kl2 = KeywordLabel(language=Language.objects.get(id='en'), name='asdfgh')
    kl2.save()
    keyword.alt_labels.add(kl)
    keyword2.alt_labels.add(kl2)

    matcher = KeywordMatcher()
    assert set([keyword2]) == set(matcher.match('asdfghe'))
