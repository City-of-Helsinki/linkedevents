# -*- coding: utf-8 -*-

from .utils import versioned_reverse as reverse
import pytest
from .utils import get


def get_detail(api_client, detail_pk, version='v1', data=None):
    detail_url = reverse('keywordset-detail', version=version, kwargs={'pk': detail_pk})
    return get(api_client, detail_url, data=data)


@pytest.mark.django_db
def test_keywordset_excludes_hidden_keywords(api_client, keyword, keyword_set2):
    keyword.is_hidden = True
    keyword.save()
    keyword_set2.save()
    response = get_detail(api_client, keyword_set2.pk, data={'include': 'keywords'})
    assert response.status_code == 200
    for set_keyword in response.data.get('keywords'):
        assert set_keyword.get('id') != keyword.id


@pytest.mark.django_db
def test_keywordset_does_not_exclude_non_hidden_keywords(api_client, keyword, keyword_set2):
    keyword.is_hidden = False
    keyword.save()
    keyword_set2.save()
    response = get_detail(api_client, keyword_set2.pk, data={'include': 'keywords'})
    assert response.status_code == 200
    found = False
    for set_keyword in response.data.get('keywords'):
        if set_keyword.get('id') == keyword.id:
            found = True
    assert found == True