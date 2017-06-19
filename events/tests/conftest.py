# -*- coding: utf-8 -*-
from datetime import timedelta

# django
from django.contrib.auth import get_user_model
from django.utils import timezone
from .utils import versioned_reverse as reverse
from .test_event_get import get_list
from django.contrib.gis.geos import Point, Polygon, MultiPolygon
from munigeo.models import (AdministrativeDivision, AdministrativeDivisionType, AdministrativeDivisionGeometry,
                            Municipality)

# 3rd party
import pytest
from rest_framework.test import APIClient


# events 
from events.models import (
    DataSource, Organization, Place, Language, Keyword, KeywordLabel, Event,
    Offer)
from events.api import (
    KeywordSerializer, PlaceSerializer, LanguageSerializer
)
from django.conf import settings

from ..models import License, PublicationStatus

TEXT = 'testing'
URL = "http://localhost"
DATETIME = (timezone.now() + timedelta(days=1)).isoformat().replace('+00:00', 'Z')

OTHER_DATA_SOURCE_ID = "testotherdatasourceid"

@pytest.fixture
def kw_name():
    return 'known_keyword'

@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
@pytest.fixture
def data_source():
    return DataSource.objects.create(
        id=settings.SYSTEM_DATA_SOURCE_ID,
        api_key="test_api_key",
        user_editable=True
    )


@pytest.mark.django_db
@pytest.fixture
def other_data_source():
    return DataSource.objects.create(
        id=OTHER_DATA_SOURCE_ID,
        api_key="test_api_key2"
    )


@pytest.mark.django_db
@pytest.fixture
def user():
    return get_user_model().objects.create(
        username='test_user',
        first_name='Cem',
        last_name='Kaner',
        email='cem@kaner.com'
    )


@pytest.mark.django_db
@pytest.fixture
def user2():
    return get_user_model().objects.create(
        username='test_user2',
        first_name='Brendan',
        last_name='Neutra',
        email='brendan@neutra.com'
    )


@pytest.mark.django_db
@pytest.fixture
def organization(data_source, user):
    org, created = Organization.objects.get_or_create(
        id=data_source.id + ':test_organization',
        name="test_organization",
        data_source=data_source,
    )
    org.admin_users.add(user)
    org.save()
    return org


@pytest.mark.django_db
@pytest.fixture
def organization2(other_data_source, user2):
    org, created = Organization.objects.get_or_create(
        id=other_data_source.id + ':test_organization2',
        name="test_organization2",
        data_source=other_data_source,
    )
    org.admin_users.add(user2)
    org.save()
    return org


@pytest.mark.django_db
@pytest.fixture
def offer(event2):
    return Offer.objects.create(event=event2, is_free=True)

@pytest.mark.django_db
@pytest.fixture
def minimal_event_dict(data_source, organization, location_id):
    return {
        'name': {'fi': TEXT},
        'publication_status': 'public',
        'start_time': DATETIME,
        'location': {'@id': location_id},
        'keywords': [
            {'@id': keyword_id(data_source, 'test')},
        ],
        'short_description': {'fi': 'short desc', 'sv': 'short desc sv', 'en': 'short desc en'},
        'description': {'fi': 'desc', 'sv': 'desc sv', 'en': 'desc en'},
        'offers': [
            {
                'is_free': False,
                'price': {'en': TEXT, 'sv': TEXT, 'fi': TEXT},
                'description': {'en': TEXT, 'sv': TEXT, 'fi': TEXT},
                'info_url': {'en': URL, 'sv': URL, 'fi': URL}
            }
        ]
    }


@pytest.fixture
def municipality():
    return Municipality.objects.create(
        name='test municipality',
    )


@pytest.fixture
def administrative_division_type():
    return AdministrativeDivisionType.objects.create(type='neighborhood', name='test neighborhood division type')


@pytest.fixture
def administrative_division_type2():
    return AdministrativeDivisionType.objects.create(type='district', name='test district division type')


@pytest.fixture
def administrative_division(administrative_division_type, municipality):
    division = AdministrativeDivision.objects.create(
        name_en='test division',
        type=administrative_division_type,
        ocd_id='ocd-division/test:1',
        municipality=municipality,
    )
    coords = ((0, 0), (0, 200), (200, 200), (200, 0), (0, 0))
    AdministrativeDivisionGeometry.objects.create(division=division, boundary=MultiPolygon([Polygon(coords)]))
    return division


@pytest.fixture
def administrative_division2(administrative_division_type):
    division = AdministrativeDivision.objects.create(
        name_en='test division 2',
        type=administrative_division_type,
        ocd_id='ocd-division/test:2'
    )
    coords = ((100, 100), (100, 300), (300, 300), (300, 100), (100, 100))
    AdministrativeDivisionGeometry.objects.create(division=division, boundary=MultiPolygon([Polygon(coords)]))
    return division


@pytest.mark.django_db
@pytest.fixture
def place(data_source, organization, administrative_division):
    return Place.objects.create(
        id=data_source.id + ':test_location',
        data_source=data_source,
        publisher=organization,
        position=Point(50, 50)
    )


@pytest.mark.django_db
@pytest.fixture
def event(data_source, organization, place, user):
    return Event.objects.create(
        id=data_source.id + ':test_event', location=place,
        data_source=data_source, publisher=organization,
        last_modified_by=user,
        start_time=timezone.now() + timedelta(minutes=30),
        end_time=timezone.now() + timedelta(hours=1),
        short_description='short desc',
        description='desc',
        name='event'
    )


@pytest.mark.django_db
@pytest.fixture
def place2(other_data_source, organization2):
    return Place.objects.create(
        id=other_data_source.id + ':test_location_2',
        data_source=other_data_source,
        publisher=organization2
    )


@pytest.fixture
def place3(data_source, organization):
    return Place.objects.create(
        id=data_source.id + ':test_location_3',
        data_source=data_source,
        publisher=organization
    )


@pytest.mark.django_db
@pytest.fixture
def event2(other_data_source, organization2, place2, user2, keyword):
    return Event.objects.create(
        id=other_data_source.id + ':test_event_2', location=place2,
        data_source=other_data_source, publisher=organization2,
        last_modified_by=user2,
        start_time=timezone.now() + timedelta(minutes=30),
        end_time=timezone.now() + timedelta(hours=1),
        short_description='short desc',
        description='desc',
        name='event2'
    )

@pytest.fixture
def event3(place3, user):
    return Event.objects.create(
        id=place3.data_source.id + ':test_event_3', location=place3,
        data_source=place3.data_source, publisher=place3.publisher,
        last_modified_by=user,
        start_time=timezone.now() + timedelta(minutes=30),
        end_time=timezone.now() + timedelta(hours=1),
        short_description='short desc',
        description='desc',
        name='event3'
    )


@pytest.mark.django_db
@pytest.fixture
def draft_event(place, user):
    return Event.objects.create(
        id=place.data_source.id + ':test_event', location=place,
        data_source=place.data_source, publisher=place.publisher,
        last_modified_by=user,
        publication_status=PublicationStatus.DRAFT,
        start_time=timezone.now(),
        end_time=timezone.now()
    )


@pytest.mark.django_db
@pytest.fixture
def location_id(place):
    obj_id = reverse(PlaceSerializer().view_name, kwargs={'pk': place.id})
    return obj_id


@pytest.mark.django_db
@pytest.fixture
def keyword(data_source, kw_name):
    lang_objs = [
        Language.objects.get_or_create(id=lang)[0]
        for lang in ['fi', 'sv', 'en']
    ]

    labels = [
        KeywordLabel.objects.create(
            name='%s%s' % (kw_name, lang.id),
            language=lang
        )
        for lang in lang_objs
    ]

    obj = Keyword.objects.create(
        id=data_source.id + ':' + kw_name,
        name=kw_name,
        data_source=data_source
    )
    for label in labels:
        obj.alt_labels.add(label)
    obj.save()

    return obj



@pytest.mark.django_db
@pytest.fixture
def keyword_id(data_source, kw_name):
    obj = keyword(data_source, kw_name)
    obj_id = reverse(KeywordSerializer().view_name, kwargs={'pk': obj.id})
    return obj_id


@pytest.mark.django_db
@pytest.fixture
def languages():
    lang_objs = [
        Language.objects.get_or_create(id=lang)[0]
        for lang in ['fi', 'sv', 'en']
    ]
    return lang_objs


def language_id(language):
    obj_id = reverse(LanguageSerializer().view_name, kwargs={'pk': language.pk})
    return obj_id


@pytest.mark.django_db
@pytest.fixture
def complex_event_dict(data_source, organization, location_id, languages):
    return {
        'publisher': organization.id,
        'name': {'en': TEXT, 'sv': TEXT, 'fi': TEXT},
        'event_status': 'EventScheduled',
        'location': {'@id': location_id},
        'keywords': [
            {'@id': keyword_id(data_source, 'simple')},
            {'@id': keyword_id(data_source, 'test')},
            {'@id': keyword_id(data_source, 'keyword')},
        ],
        'audience': [
            {'@id': keyword_id(data_source, 'test_audience1')},
            {'@id': keyword_id(data_source, 'test_audience2')},
            {'@id': keyword_id(data_source, 'test_audience3')},
        ],
        'external_links': [
            {'name': TEXT, 'link': URL, 'language': 'fi'},
            {'name': TEXT, 'link': URL, 'language': 'sv'},
            {'name': TEXT, 'link': URL, 'language': 'en'},
        ],
        'offers': [
            {
                'is_free': False,
                'price': {'en': TEXT, 'sv': TEXT, 'fi': TEXT},
                'description': {'en': TEXT, 'sv': TEXT, 'fi': TEXT},
                'info_url': {'en': URL, 'sv': URL, 'fi': URL}
            }
        ],
        'in_language': [
            {"@id": language_id(languages[0])},
            {"@id": language_id(languages[1])},
        ],
        'custom_data': {'my': 'data', 'your': 'data'},
        'origin_id': TEXT,
        'date_published': DATETIME,
        'start_time': DATETIME,
        'end_time': DATETIME,
        'location_extra_info': {'fi': TEXT},
        'info_url': {'en': URL, 'sv': URL, 'fi': URL},
        'secondary_headline': {'en': TEXT, 'sv': TEXT, 'fi': TEXT},
        'description': {'en': TEXT, 'sv': TEXT, 'fi': TEXT},
        'headline': {'en': TEXT, 'sv': TEXT, 'fi': TEXT},
        'short_description': {'en': TEXT, 'sv': TEXT, 'fi': TEXT},
        'provider': {'en': TEXT, 'sv': TEXT, 'fi': TEXT},
        'publication_status': 'public',
    }


@pytest.fixture
def api_get_list(request, event, api_client):
    """
    Return an API get_list requestor with version set on
    the module of the test function, or use default API version
    """
    version = getattr(request.module, "version", "v1")

    def f():
        return get_list(api_client, version)
    return f


@pytest.fixture(params=['v1', 'v0.1'])
def all_api_get_list(request, event, api_client):
    """
    Return an API get_list requestor with version set on
    the module of the test function, or use default API version
    """
    version = request.param

    def f():
        return get_list(api_client, version)
    return f


# These initial licenses are created by a migration, but because of a feature
# related to Django testing, objects created in datamigrations aren't available
# in all testcases, so we need to create those here too to be sure they exist.
@pytest.fixture(autouse=True)
def create_initial_licenses():
    License.objects.get_or_create(
        id='event_only',
        defaults={
            'name_fi': 'Vain tapahtuman markkinointiin',
            'name_sv': 'Endast för marknadsföring av evenemanget',
            'name_en': 'For event marketing only',
            'url': '',
        }
    )
    License.objects.get_or_create(
        id='cc_by',
        defaults={
            'name_fi': 'Nimeä 4.0 Kansainvälinen (CC BY 4.0)',
            'name_sv': 'Erkännande 4.0 Internationell (CC BY 4.0)',
            'name_en': 'Attribution 4.0 International (CC BY 4.0)',
            'url': 'https://creativecommons.org/licenses/by/4.0/',
        }
    )
