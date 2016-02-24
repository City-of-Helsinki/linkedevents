# -*- coding: utf-8 -*-
import pytest
from .utils import versioned_reverse as reverse

from events.tests.utils import assert_event_data_is_equal
from events.models import Event
from events.api import SYSTEM_DATA_SOURCE_ID

from .test_event_get import get_detail
from ..models import PublicationStatus

@pytest.mark.django_db
def test__user_sees_auth_fields(api_client, event, user, user2, organization, organization2):
    """
    Authenticated user can see publication_status field
    """

    api_client.force_authenticate(user=user)

    response = get_detail(api_client, event.pk)

    assert response.data.get('publication_status') == "public"


@pytest.mark.django_db
def test__insivible_auth_fields(api_client, event, user, user2, organization, organization2):
    """
    Not authenticated user can't see publication_status field
    """
    response = get_detail(api_client, event.pk)

    assert response.data.get('publication_status') is None



@pytest.mark.django_db
def test__draft_visibility(api_client, draft_event, user, user2, organization, organization2):
    """
    Not authenticated user can't see publication_status field
    """

    # draft_event is created by user and should be visible
    api_client.force_authenticate(user=user)
    detail_url = reverse('event-detail', kwargs={'pk': draft_event.pk})
    response = api_client.get(detail_url, format='json')

    assert response.data.get('publication_status') == 'draft'

    # user2 is in different organization and should not see draft_event
    api_client.force_authenticate(user=user2)
    response = api_client.get(detail_url, format='json')

    assert response.status_code == 404
