import pytest


@pytest.mark.django_db
def test_keyword_cannot_replace_itself(keyword):
    keyword.replaced_by = keyword
    keyword.deprecated = True
    with pytest.raises(Exception):
        keyword.save()


@pytest.mark.django_db
def test_prevent_circular_keyword_replacement(keyword, keyword2, keyword3):
    keyword.replaced_by = keyword2
    keyword.save()
    keyword2.replaced_by = keyword3
    keyword2.save()
    keyword3.replaced_by = keyword
    with pytest.raises(Exception):
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
