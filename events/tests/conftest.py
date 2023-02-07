from datetime import datetime, timedelta

# 3rd party
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon

# django
from django.core.management import call_command
from django.utils import timezone
from django_orghierarchy.models import Organization
from munigeo.models import (
    AdministrativeDivision,
    AdministrativeDivisionGeometry,
    AdministrativeDivisionType,
    Municipality,
)
from rest_framework.test import APIClient

from events.api import KeywordSerializer, LanguageSerializer, PlaceSerializer

# events
from events.models import (
    DataSource,
    Event,
    Keyword,
    KeywordLabel,
    KeywordSet,
    Language,
    Offer,
    Place,
)
from registrations.models import Registration

from ..models import License, PublicationStatus
from .test_event_get import get_list
from .utils import versioned_reverse as reverse

TEXT_FI = "testaus"
TEXT_SV = "testning"
TEXT_EN = "testing"
URL = "http://localhost"
DATETIME = (timezone.now() + timedelta(days=1)).isoformat().replace("+00:00", "Z")

OTHER_DATA_SOURCE_ID = "testotherdatasourceid"


# Django test harness tries to serialize DB in order to support transactions
# within tests. (It restores the snapshot after such tests).
# This fails with modeltranslate, as the serialization is done before
# sync_translation_fields has a chance to run. Thus the fields are missing
# and serialization fails horribly.
@pytest.fixture(scope="session")
def django_db_modify_db_settings(django_db_modify_db_settings_xdist_suffix):
    settings.DATABASES["default"]["TEST"]["SERIALIZE"] = False


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("sync_translation_fields", "--noinput")


@pytest.fixture
def kw_name():
    return "tunnettu_avainsana"


@pytest.fixture
def kw_name_2():
    return "known_keyword"


@pytest.fixture
def kw_name_3():
    return "känd_nyckelord"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture()
def user_api_client(user):
    api_client = APIClient()
    api_client.force_authenticate(user)
    return api_client


@pytest.mark.django_db
@pytest.fixture
def data_source():
    return DataSource.objects.create(
        id=settings.SYSTEM_DATA_SOURCE_ID,
        api_key="test_api_key",
        user_editable_resources=True,
        user_editable_organizations=True,
    )


@pytest.mark.django_db
@pytest.fixture
def other_data_source():
    return DataSource.objects.create(id=OTHER_DATA_SOURCE_ID, api_key="test_api_key2")


@pytest.mark.django_db
@pytest.fixture
def user():
    return get_user_model().objects.create(
        username="test_user", first_name="Cem", last_name="Kaner", email="cem@kaner.com"
    )


@pytest.mark.django_db
@pytest.fixture
def user2():
    return get_user_model().objects.create(
        username="test_user2",
        first_name="Brendan",
        last_name="Neutra",
        email="brendan@neutra.com",
    )


@pytest.mark.django_db
@pytest.fixture
def super_user():
    return get_user_model().objects.create(
        username="super_user",
        first_name="Super",
        last_name="Man",
        email="super@user.com",
        is_superuser=True,
    )


@pytest.mark.django_db
@pytest.fixture
def organization(data_source, user):
    org, created = Organization.objects.get_or_create(
        id=data_source.id + ":test_organization",
        origin_id="test_organization",
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
        id=other_data_source.id + ":test_organization2",
        origin_id="test_organization2",
        name="test_organization2",
        data_source=other_data_source,
    )
    org.admin_users.add(user2)
    org.save()
    return org


@pytest.mark.django_db
@pytest.fixture
def organization3(other_data_source, user2):
    org, created = Organization.objects.get_or_create(
        id=other_data_source.id + ":test_organization3",
        origin_id="test_organization3",
        name="test_organization3",
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
@pytest.fixture(scope="class")
def make_minimal_event_dict(make_keyword_id):
    def _make_minimal_event_dict(data_source, organization, location_id):
        return {
            "type_id": "General",
            "name": {"fi": TEXT_FI},
            "start_time": datetime.strftime(
                timezone.now() + timedelta(days=1), "%Y-%m-%d"
            ),
            "location": {"@id": location_id},
            "keywords": [
                {"@id": make_keyword_id(data_source, organization, "test")},
            ],
            "short_description": {
                "fi": "short desc",
                "sv": "short desc sv",
                "en": "short desc en",
            },
            "description": {"fi": "desc", "sv": "desc sv", "en": "desc en"},
            "offers": [
                {
                    "is_free": False,
                    "price": {"en": TEXT_EN, "sv": TEXT_SV, "fi": TEXT_FI},
                    "description": {"en": TEXT_EN, "sv": TEXT_SV, "fi": TEXT_FI},
                    "info_url": {"en": URL, "sv": URL, "fi": URL},
                }
            ],
            "publisher": organization.id,
        }

    return _make_minimal_event_dict


@pytest.mark.django_db
@pytest.fixture
def minimal_event_dict(data_source, organization, location_id, make_minimal_event_dict):
    return make_minimal_event_dict(data_source, organization, location_id)


@pytest.mark.django_db
@pytest.fixture(scope="class")
def make_minimal_event_dict_class(request, make_minimal_event_dict):
    def _make_minimal_event_dict(self, *args):
        return make_minimal_event_dict(*args)

    request.cls.make_minimal_event_dict = _make_minimal_event_dict


@pytest.fixture
def municipality():
    return Municipality.objects.create(
        name="test municipality",
    )


@pytest.fixture
def administrative_division_type():
    return AdministrativeDivisionType.objects.create(
        type="neighborhood", name="test neighborhood division type"
    )


@pytest.fixture
def administrative_division_type2():
    return AdministrativeDivisionType.objects.create(
        type="district", name="test district division type"
    )


@pytest.fixture
def administrative_division(administrative_division_type, municipality):
    division = AdministrativeDivision.objects.create(
        name="test division",
        type=administrative_division_type,
        ocd_id="ocd-division/test:1",
        municipality=municipality,
    )
    coords = ((0, 0), (0, 200), (200, 200), (200, 0), (0, 0))
    AdministrativeDivisionGeometry.objects.create(
        division=division, boundary=MultiPolygon([Polygon(coords)])
    )
    return division


@pytest.fixture
def administrative_division2(administrative_division_type):
    division = AdministrativeDivision.objects.create(
        name_en="test division 2",
        type=administrative_division_type,
        ocd_id="ocd-division/test:2",
    )
    coords = ((100, 100), (100, 300), (300, 300), (300, 100), (100, 100))
    AdministrativeDivisionGeometry.objects.create(
        division=division, boundary=MultiPolygon([Polygon(coords)])
    )
    return division


@pytest.mark.django_db
@pytest.fixture
def place_dict(data_source, organization):
    return {
        "data_source": data_source.id,
        "origin_id": "testi-1234",
        "publisher": organization.id,
        "position": {
            "type": "Point",
            "coordinates": [384574.0894343857, 6672362.664316102],
        },
        "email": "testi@example.com",
        "postal_code": "00100",
        "name": {"en": "Test location", "fi": "Testipaikka"},
        "description": {"en": "Testipaikka - en", "fi": "Testipaikka - fi"},
        "street_address": {"en": "Teststreet 1", "fi": "Testikuja 1"},
        "address_locality": {"en": "Testilä", "fi": "Testilä"},
    }


@pytest.mark.django_db
@pytest.fixture
def place(data_source, organization, administrative_division):
    return Place.objects.create(
        id=data_source.id + ":test_location",
        data_source=data_source,
        publisher=organization,
        position=Point(50, 50),
        name_fi="Paikka 1",
    )


@pytest.mark.django_db
@pytest.fixture
def make_event(data_source, organization, place, user):
    def _make_event(origin_id, start_time=None, end_time=None):
        if not start_time:
            event_status = Event.Status.POSTPONED
        else:
            event_status = Event.Status.SCHEDULED
        return Event.objects.create(
            id=data_source.id + ":" + origin_id,
            location=place,
            data_source=data_source,
            publisher=organization,
            event_status=event_status,
            last_modified_by=user,
            start_time=start_time,
            end_time=end_time,
            has_start_time=start_time is not None,
            has_end_time=end_time is not None,
            short_description="short desc",
            description="desc",
            name="tapahtuma",
        )

    return _make_event


@pytest.mark.django_db
@pytest.fixture
def event(data_source, organization, place, user):
    return Event.objects.create(
        id=data_source.id + ":test_event",
        location=place,
        data_source=data_source,
        publisher=organization,
        last_modified_by=user,
        start_time=timezone.now() + timedelta(minutes=30),
        end_time=timezone.now() + timedelta(hours=1),
        short_description="short desc",
        description="desc",
        name="tapahtuma",
    )


@pytest.mark.django_db
@pytest.fixture
def past_event(data_source, organization, place, user):
    return Event.objects.create(
        id=data_source.id + ":past_test_event",
        location=place,
        data_source=data_source,
        publisher=organization,
        last_modified_by=user,
        start_time=timezone.now() - timedelta(hours=10),
        end_time=timezone.now() - timedelta(hours=9),
        short_description="short desc",
        description="desc",
        name="tapahtuma",
    )


@pytest.mark.django_db
@pytest.fixture
def place2(other_data_source, organization2):
    return Place.objects.create(
        id=other_data_source.id + ":test_location_2",
        data_source=other_data_source,
        publisher=organization2,
        position=Point(0, 0),
        name_en="Place 2",
    )


@pytest.fixture
def place3(data_source, organization):
    return Place.objects.create(
        id=data_source.id + ":test_location_3",
        data_source=data_source,
        publisher=organization,
        name_sv="Plats 3",
    )


@pytest.mark.django_db
@pytest.fixture
def event2(other_data_source, organization2, place2, user2, keyword):
    return Event.objects.create(
        id=other_data_source.id + ":test_event_2",
        location=place2,
        data_source=other_data_source,
        publisher=organization2,
        last_modified_by=user2,
        start_time=timezone.now() + timedelta(minutes=30),
        end_time=timezone.now() + timedelta(hours=1),
        short_description="short desc",
        description="desc",
        name="event",
    )


@pytest.fixture
def event3(place3, user):
    return Event.objects.create(
        id=place3.data_source.id + ":test_event_3",
        location=place3,
        data_source=place3.data_source,
        publisher=place3.publisher,
        last_modified_by=user,
        start_time=timezone.now() + timedelta(minutes=30),
        end_time=timezone.now() + timedelta(hours=1),
        short_description="short desc",
        description="desc",
        name="evenemang",
    )


@pytest.fixture
def event4(place3, user):
    return Event.objects.create(
        id=place3.data_source.id + ":test_event_4",
        location=place3,
        data_source=place3.data_source,
        publisher=place3.publisher,
        last_modified_by=user,
        start_time=timezone.now() + timedelta(minutes=30),
        end_time=timezone.now() + timedelta(hours=1),
        short_description="short desc",
        description="desc",
        name="evenemang",
    )


@pytest.mark.django_db
@pytest.fixture
def draft_event(place, user):
    return Event.objects.create(
        id=place.data_source.id + ":test_event",
        location=place,
        data_source=place.data_source,
        publisher=place.publisher,
        last_modified_by=user,
        publication_status=PublicationStatus.DRAFT,
        start_time=timezone.now(),
        end_time=timezone.now(),
    )


@pytest.mark.django_db
@pytest.fixture
def location_id(place):
    obj_id = reverse(PlaceSerializer().view_name, kwargs={"pk": place.id})
    return obj_id


@pytest.mark.django_db
@pytest.fixture
def make_location_id():
    def _make_location_id(place):
        obj_id = reverse(PlaceSerializer().view_name, kwargs={"pk": place.id})
        return obj_id

    return _make_location_id


@pytest.mark.django_db
@pytest.fixture
def keyword_dict(data_source, organization):
    return {
        "origin_id": "testi-12345",
        "data_source": data_source.id,
        "publisher": organization.id,
        "name": {
            "fi": "Testi avainsana",
            "en": "Test keyword",
        },
    }


@pytest.mark.django_db
@pytest.fixture(scope="class")
def make_keyword():
    def _make_keyword(data_source, organization, kw_name):
        lang_objs = [
            Language.objects.get_or_create(id=lang)[0] for lang in ["fi", "sv", "en"]
        ]

        labels = [
            KeywordLabel.objects.create(name="%s%s" % (kw_name, lang.id), language=lang)
            for lang in lang_objs
        ]

        obj = Keyword.objects.create(
            id=data_source.id + ":" + kw_name,
            name=kw_name,
            publisher=organization,
            data_source=data_source,
        )
        for label in labels:
            obj.alt_labels.add(label)
        obj.save()

        return obj

    return _make_keyword


@pytest.mark.django_db
@pytest.fixture
def keyword(data_source, organization, kw_name, make_keyword):
    return make_keyword(data_source, organization, kw_name)


@pytest.mark.django_db
@pytest.fixture
def keyword2(data_source, organization, kw_name_2, make_keyword):
    return make_keyword(data_source, organization, kw_name_2)


@pytest.mark.django_db
@pytest.fixture
def keyword3(data_source, organization, kw_name_3, make_keyword):
    return make_keyword(data_source, organization, kw_name_3)


@pytest.mark.django_db
@pytest.fixture(scope="class")
def make_keyword_id(make_keyword):
    def _make_keyword_id(data_source, organization, kw_name):
        obj = make_keyword(data_source, organization, kw_name)
        obj_id = reverse(KeywordSerializer().view_name, kwargs={"pk": obj.id})
        return obj_id

    return _make_keyword_id


@pytest.mark.django_db
@pytest.fixture
def keyword_id(data_source, organization, kw_name, make_keyword_id):
    return make_keyword_id(data_source, organization, kw_name)


@pytest.mark.django_db
@pytest.fixture
def keyword_set(data_source, keyword, keyword2):
    kw_set = KeywordSet.objects.create(
        data_source=data_source, name="name1", id="set:1"
    )
    kw_set.keywords.set([keyword, keyword2])
    return kw_set


@pytest.mark.django_db
@pytest.fixture
def keyword_set2(data_source, keyword3):
    kw_set = KeywordSet.objects.create(
        data_source=data_source, name="name2", id="set:2"
    )
    kw_set.keywords.set([keyword3])
    return kw_set


@pytest.mark.django_db
@pytest.fixture
def languages():
    lang_objs = [
        Language.objects.get_or_create(id=lang)[0] for lang in ["fi", "sv", "en"]
    ]
    return lang_objs


@pytest.mark.django_db
@pytest.fixture
def keywordlabel(kw_name, languages):
    return KeywordLabel.objects.create(name=kw_name, language=languages[0])


@pytest.mark.django_db
@pytest.fixture(scope="class")
def languages_class(request):
    lang_objs = [
        Language.objects.get_or_create(id=lang)[0] for lang in ["fi", "sv", "en"]
    ]
    request.cls.languages = lang_objs


def language_id(language):
    obj_id = reverse(LanguageSerializer().view_name, kwargs={"pk": language.pk})
    return obj_id


@pytest.mark.django_db
@pytest.fixture(scope="class")
def make_complex_event_dict(make_keyword_id):
    def _make_complex_event_dict(data_source, organization, location_id, languages):
        return {
            "publisher": organization.id,
            "data_source": data_source.id,
            "name": {"en": TEXT_EN, "sv": TEXT_SV, "fi": TEXT_FI},
            "event_status": "EventScheduled",
            "type_id": "General",
            "location": {"@id": location_id},
            "keywords": [
                {"@id": make_keyword_id(data_source, organization, "simple")},
                {"@id": make_keyword_id(data_source, organization, "test")},
                {"@id": make_keyword_id(data_source, organization, "keyword")},
            ],
            "audience": [
                {"@id": make_keyword_id(data_source, organization, "test_audience1")},
                {"@id": make_keyword_id(data_source, organization, "test_audience2")},
                {"@id": make_keyword_id(data_source, organization, "test_audience3")},
            ],
            "external_links": [
                {"name": TEXT_FI, "link": URL, "language": "fi"},
                {"name": TEXT_SV, "link": URL, "language": "sv"},
                {"name": TEXT_EN, "link": URL, "language": "en"},
            ],
            "videos": [
                {"name": TEXT_FI, "url": URL, "alt_text": TEXT_FI},
            ],
            "offers": [
                {
                    "is_free": False,
                    "price": {"en": TEXT_EN, "sv": TEXT_SV, "fi": TEXT_FI},
                    "description": {"en": TEXT_EN, "sv": TEXT_SV, "fi": TEXT_FI},
                    "info_url": {"en": URL, "sv": URL, "fi": URL},
                }
            ],
            "in_language": [
                {"@id": language_id(languages[0])},
                {"@id": language_id(languages[1])},
            ],
            "custom_data": {"my": "data", "your": "data"},
            "origin_id": TEXT_FI,
            "date_published": DATETIME,
            "start_time": DATETIME,
            "end_time": DATETIME,
            "location_extra_info": {"fi": TEXT_FI},
            "info_url": {"en": URL, "sv": URL, "fi": URL},
            "secondary_headline": {"en": TEXT_EN, "sv": TEXT_SV, "fi": TEXT_FI},
            "description": {"en": TEXT_EN, "sv": TEXT_SV, "fi": TEXT_FI},
            "headline": {"en": TEXT_EN, "sv": TEXT_SV, "fi": TEXT_FI},
            "short_description": {"en": TEXT_EN, "sv": TEXT_SV, "fi": TEXT_FI},
            "provider": {"en": TEXT_EN, "sv": TEXT_SV, "fi": TEXT_FI},
            "provider_contact_info": {"en": TEXT_EN, "sv": TEXT_SV, "fi": TEXT_FI},
            "audience_min_age": 5,
            "audience_max_age": 15,
        }

    return _make_complex_event_dict


@pytest.mark.django_db
@pytest.fixture
def complex_event_dict(
    data_source, organization, location_id, languages, make_complex_event_dict
):
    return make_complex_event_dict(data_source, organization, location_id, languages)


@pytest.mark.django_db
@pytest.fixture(scope="class")
def make_complex_event_dict_class(request, make_complex_event_dict):
    def _make_complex_event_dict(self, *args):
        return make_complex_event_dict(*args)

    request.cls.make_complex_event_dict = _make_complex_event_dict


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


@pytest.fixture(params=["v1", "v0.1"])
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
        id="event_only",
        defaults={
            "name_fi": "Vain tapahtuman markkinointiin",
            "name_sv": "Endast för marknadsföring av evenemanget",
            "name_en": "For event marketing only",
            "url": "",
        },
    )
    License.objects.get_or_create(
        id="cc_by",
        defaults={
            "name_fi": "Nimeä 4.0 Kansainvälinen (CC BY 4.0)",
            "name_sv": "Erkännande 4.0 Internationell (CC BY 4.0)",
            "name_en": "Attribution 4.0 International (CC BY 4.0)",
            "url": "https://creativecommons.org/licenses/by/4.0/",
        },
    )


@pytest.fixture(scope="session", autouse=True)
def setup_env():
    settings.SUPPORT_EMAIL = "test@test.com"
    settings.JWT_AUTH[
        "JWT_SECRET_KEY"
    ] = "abcdefghacbdefgabcdefghacbdefgabcdefghacbdefgabcdefghacbdefgabcdefghacbdefg"


@pytest.mark.django_db
@pytest.fixture
def registration(event, user):
    return Registration.objects.create(
        event=event,
        audience_min_age=6,
        audience_max_age=18,
        created_by=user,
        last_modified_by=user,
        enrolment_start_time=datetime.now(),
        enrolment_end_time=datetime.now() + timedelta(days=10),
        confirmation_message="Your registration is confirmed",
        maximum_attendee_capacity=20,
        waiting_list_capacity=20,
    )


@pytest.mark.django_db
@pytest.fixture
def registration2(event2, user2):
    return Registration.objects.create(
        event=event2,
        audience_min_age=6,
        audience_max_age=18,
        created_by=user2,
        last_modified_by=user2,
        enrolment_start_time=datetime.now(),
        enrolment_end_time=datetime.now() + timedelta(days=10),
        confirmation_message="Your registration is confirmed",
        maximum_attendee_capacity=20,
        waiting_list_capacity=20,
    )


@pytest.mark.django_db
@pytest.fixture
def registration3(event3, user):
    return Registration.objects.create(
        event=event3,
        audience_min_age=6,
        audience_max_age=18,
        created_by=user,
        last_modified_by=user,
        confirmation_message="Your registration is confirmed",
        waiting_list_capacity=20,
    )


@pytest.mark.django_db
@pytest.fixture
def registration4(event4, user):
    return Registration.objects.create(
        event=event4,
        audience_min_age=6,
        audience_max_age=18,
        created_by=user,
        last_modified_by=user,
        confirmation_message="Your registration is confirmed",
        waiting_list_capacity=20,
    )
