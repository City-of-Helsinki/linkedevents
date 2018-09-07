# -*- coding: utf-8 -*-

from .utils import versioned_reverse as reverse
import pytest
from .utils import get


def get_list(api_client, version='v1', data=None):
    list_url = reverse('keyword-list', version=version)
    return get(api_client, list_url, data=data)


def get_detail(api_client, detail_pk, version='v1', data=None):
    detail_url = reverse('keyword-detail', version=version, kwargs={'pk': detail_pk})
    return get(api_client, detail_url, data=data)


@pytest.mark.django_db
def test_get_keyword_detail(api_client, keyword):
    response = get_detail(api_client, keyword.pk)
    assert response.data['id'] == keyword.id


@pytest.mark.django_db
def test_get_unknown_keyword_detail_check_404(api_client):
    response = api_client.get(reverse('keyword-detail', kwargs={'pk': 'möö'}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_get_keyword_list_verify_text_filter(api_client, keyword, keyword2, keyword3):
    response = api_client.get(reverse('keyword-list'), data={'text': 'avainsana',
                                                             'show_all_keywords': True})
    assert keyword.id in [entry['id'] for entry in response.data['data']]
    assert keyword2.id not in [entry['id'] for entry in response.data['data']]
    assert keyword3.id not in [entry['id'] for entry in response.data['data']]
