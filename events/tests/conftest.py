# -*- coding: utf-8 -*-

# django
from django.contrib.auth import get_user_model

# 3rd party
import pytest
from rest_framework.test import APIClient

# events 
from events.models import DataSource, Organization


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
@pytest.fixture
def data_source():
    return DataSource.objects.create(id='test_data_source')


@pytest.mark.django_db
@pytest.fixture
def organization(data_source):
    return Organization.objects.create(
        id='test_organization',
        data_source=data_source
    )


@pytest.mark.django_db
@pytest.fixture
def minimal_event_dict(data_source, organization):
    return {
        "data_source": data_source.id,
        "publisher": organization.id,
        "name": {"fi": 'minimal_event'}
    }


@pytest.mark.django_db
@pytest.fixture
def user():
    return get_user_model().objects.create(
        username='test_user',
        first_name='Cem',
        last_name='Kaner',
        email='cem@kaner.com'
    )
