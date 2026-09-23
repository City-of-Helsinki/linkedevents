import pytest
from django.db import connections
from django.test.utils import CaptureQueriesContext

from events.tests.utils import versioned_reverse as reverse


@pytest.mark.django_db
def test_expanded_keyword_set_query_count_does_not_grow_per_keyword(
    api_client, keyword_set, keyword3
):
    detail_url = reverse("keywordset-detail", kwargs={"pk": keyword_set.pk})
    detail_url += "?include=keywords"

    response = api_client.get(detail_url)
    assert response.status_code == 200

    with CaptureQueriesContext(connections["default"]) as queries:
        response = api_client.get(detail_url)
    assert response.status_code == 200
    two_keyword_query_count = len(queries)

    keyword_set.keywords.add(keyword3)

    with CaptureQueriesContext(connections["default"]) as queries:
        response = api_client.get(detail_url)
    assert response.status_code == 200
    assert len(queries) == two_keyword_query_count
    assert any(item["id"] == keyword3.id for item in response.data["keywords"])
