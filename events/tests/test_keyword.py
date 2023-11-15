import pytest
from rest_framework.exceptions import ValidationError

from events.api import _find_keyword_replacements
from events.tests.factories import KeywordFactory


@pytest.mark.django_db
def test_keyword_cannot_replace_itself(keyword):
    keyword.replaced_by = keyword
    keyword.deprecated = True
    with pytest.raises(ValidationError):
        keyword.save()


@pytest.mark.django_db
def test_prevent_circular_keyword_replacement(keyword, keyword2, keyword3):
    keyword.replaced_by = keyword2
    keyword.save()
    keyword2.replaced_by = keyword3
    keyword2.save()
    keyword3.replaced_by = keyword
    with pytest.raises(ValidationError):
        keyword.save()


@pytest.mark.django_db
def test_keyword_is_automatically_deprecated_on_replace(keyword, keyword2):
    keyword.replaced_by = keyword2
    keyword.save()
    assert keyword.deprecated


@pytest.mark.django_db
def test_keyword_remap_keyword_set_on_replace(keyword, keyword2, keyword3, keyword_set):
    keyword.replaced_by = keyword3
    keyword.deprecated = True
    keyword.save()
    keyword_set.refresh_from_db()
    assert set(keyword_set.keywords.all()) == set([keyword2, keyword3])


@pytest.mark.django_db
def test_keyword_remap_event_on_replace(keyword, keyword2, event):
    event.keywords.set([keyword])
    event.save()
    keyword.replaced_by = keyword2
    keyword.deprecated = True
    keyword.save()
    event.refresh_from_db()
    assert set(event.keywords.all()) == set([keyword2])
    assert set(event.audience.all()) == set()

    keyword.replaced_by = None
    keyword.deprecated = False
    keyword.save()
    event.keywords.set([])
    event.audience.set([keyword])
    event.save()
    keyword.replaced_by = keyword2
    keyword.deprecated = True
    keyword.save()
    event.refresh_from_db()
    assert set(event.keywords.all()) == set()
    assert set(event.audience.all()) == set([keyword2])


@pytest.mark.django_db
def test_keyword_get_replacement_is_none():
    keyword = KeywordFactory(deprecated=True)

    assert keyword.get_replacement() is None


@pytest.mark.django_db
def test_keyword_get_replacement_single_level():
    new_keyword = KeywordFactory()
    old_keyword = KeywordFactory(deprecated=True, replaced_by=new_keyword)

    assert old_keyword.get_replacement().pk == new_keyword.pk


@pytest.mark.django_db
def test_keyword_get_replacement_multi_level():
    new_keyword = KeywordFactory()
    old_keyword_1 = KeywordFactory(deprecated=True, replaced_by=new_keyword)
    old_keyword_2 = KeywordFactory(deprecated=True, replaced_by=old_keyword_1)

    assert old_keyword_2.get_replacement().pk == new_keyword.pk


@pytest.mark.django_db
def test_find_keyword_replacements():
    new_keyword = KeywordFactory()
    replaced_keyword = KeywordFactory(deprecated=True, replaced_by=new_keyword)
    other_keyword = KeywordFactory()
    unknown_keyword_id = "keyword:doesnotexist"

    assert _find_keyword_replacements([replaced_keyword.pk]) == ([new_keyword], True)
    assert _find_keyword_replacements([new_keyword.pk]) == ([new_keyword], True)
    assert _find_keyword_replacements([new_keyword.pk, replaced_keyword.pk]) == (
        [new_keyword],
        True,
    )
    assert _find_keyword_replacements([other_keyword.pk, unknown_keyword_id]) == (
        [other_keyword],
        False,
    )
