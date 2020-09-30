# -*- coding: utf-8 -*-
import pytest

from .utils import get
from .utils import versioned_reverse as reverse


# === util methods ===


def get_detail(api_client, detail_pk, version='v1', data=None):
    detail_url = reverse('keywordset-detail', version=version, kwargs={'pk': detail_pk})
    return get(api_client, detail_url, data=data)


# === tests ===


@pytest.mark.django_db
def test_get_keyword_set_detail(api_client, keyword_set):
    response = get_detail(api_client, keyword_set.pk)
    assert response.data['id'] == keyword_set.pk


@pytest.mark.django_db
def test_get_unknown_keyword_set_detail_check_404(api_client):
    response = api_client.get(reverse('keywordset-detail', kwargs={'pk': 'unknown'}))
    assert response.status_code == 404
