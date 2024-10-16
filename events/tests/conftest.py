from datetime import datetime, timedelta

# 3rd party
from django.contrib.gis.geos import MultiPolygon, Point, Polygon

# django
from django.utils import timezone
from django.utils.timezone import localtime
from munigeo.models import (
    AdministrativeDivision,
    AdministrativeDivisionGeometry,
    AdministrativeDivisionType,
    Municipality,
)
from parler.utils.context import switch_language

from events.api import KeywordSerializer, LanguageSerializer, PlaceSerializer

# events
from events.models import (
    Event,
    Image,
    Keyword,
    KeywordLabel,
    KeywordSet,
    Language,
    Offer,
    Place,
)
from linkedevents.tests.conftest import *  # noqa
from registrations.models import Registration

from ..models import PublicationStatus
from .utils import versioned_reverse as reverse

TEXT_FI = "testaus"
TEXT_SV = "testning"
TEXT_EN = "testing"
URL = "http://localhost"
DATETIME = (timezone.now() + timedelta(days=1)).isoformat().replace("+00:00", "Z")


@pytest.fixture(autouse=True)
def setup_env(settings):
    settings.SUPPORT_EMAIL = "test@test.com"


@pytest.fixture
def image_name():
    return "tunnettu_kuva"


@pytest.fixture
def image_name_2():
    return "known_image"


@pytest.fixture
def image_name_3():
    return "känd_bild"


@pytest.fixture
def image_url():
    return "http://fake.url/image-1/"


@pytest.fixture
def image_url_2():
    return "http://fake.url/image-2/"


@pytest.fixture
def image_url_3():
    return "http://fake.url/image-3/"


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
def kw_name_set():
    return "tunnettu_avainsanaryhmä"


@pytest.fixture
def kw_name_set_2():
    return "known_keywordset"


@pytest.fixture
def offer(event2):
    return Offer.objects.create(event=event2, is_free=True)


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


@pytest.fixture
def minimal_event_dict(data_source, organization, location_id, make_minimal_event_dict):
    return make_minimal_event_dict(data_source, organization, location_id)


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
        type=administrative_division_type,
        ocd_id="ocd-division/test:1",
        municipality=municipality,
    )
    with switch_language(division, "en"):
        division.name = "test division"
        division.save()
    coords = ((0, 0), (0, 200), (200, 200), (200, 0), (0, 0))
    AdministrativeDivisionGeometry.objects.create(
        division=division, boundary=MultiPolygon([Polygon(coords)])
    )
    return division


@pytest.fixture
def administrative_division2(administrative_division_type):
    division = AdministrativeDivision.objects.create(
        type=administrative_division_type,
        ocd_id="ocd-division/test:2",
    )
    with switch_language(division, "en"):
        division.name = "test division 2"
        division.save()
    coords = ((100, 100), (100, 300), (300, 300), (300, 100), (100, 100))
    AdministrativeDivisionGeometry.objects.create(
        division=division, boundary=MultiPolygon([Polygon(coords)])
    )
    return division


@pytest.fixture
def place_dict(data_source, organization):
    return {
        "data_source": data_source.id,
        "origin_id": "testi-1234",
        "publisher": organization.id,
        "position": {
            "type": "Point",
            "coordinates": [24.91958, 60.1718],
        },
        "email": "testi@example.com",
        "postal_code": "00100",
        "name": {"en": "Test location", "fi": "Testipaikka"},
        "description": {"en": "Testipaikka - en", "fi": "Testipaikka - fi"},
        "street_address": {"en": "Teststreet 1", "fi": "Testikuja 1"},
        "address_locality": {"en": "Testilä", "fi": "Testilä"},
    }


@pytest.fixture
def place(data_source, organization, administrative_division):
    return Place.objects.create(
        id=data_source.id + ":test_location",
        data_source=data_source,
        publisher=organization,
        position=Point(50, 50),
        name_fi="Paikka 1",
    )


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


@pytest.fixture
def location_id(place):
    obj_id = reverse(PlaceSerializer.view_name, kwargs={"pk": place.id})
    return obj_id


@pytest.fixture
def make_location_id():
    def _make_location_id(place):
        obj_id = reverse(PlaceSerializer.view_name, kwargs={"pk": place.id})
        return obj_id

    return _make_location_id


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


@pytest.fixture(scope="class")
def make_image():
    def _make_image(data_source, organization, image_name, image_url):
        return Image.objects.create(
            data_source=data_source,
            name=image_name,
            publisher=organization,
            url=image_url,
        )

    return _make_image


@pytest.fixture(scope="class")
def make_keyword():
    def _make_keyword(data_source, organization, kw_name):
        lang_objs = [
            Language.objects.get_or_create(id=lang)[0] for lang in ["fi", "sv", "en"]
        ]

        labels = [
            KeywordLabel.objects.get_or_create(
                name="%s%s" % (kw_name, lang.id), language=lang
            )[0]
            for lang in lang_objs
        ]

        obj, created = Keyword.objects.get_or_create(
            id=data_source.id + ":" + kw_name,
            defaults=dict(
                name=kw_name,
                publisher=organization,
                data_source=data_source,
            ),
        )
        for label in labels:
            obj.alt_labels.add(label)
        obj.save()

        return obj

    return _make_keyword


@pytest.fixture
def image(data_source, organization, image_name, image_url, make_image):
    return make_image(data_source, organization, image_name, image_url)


@pytest.fixture
def image2(data_source, organization, image_name_2, image_url_2, make_image):
    return make_image(data_source, organization, image_name_2, image_url_2)


@pytest.fixture
def image3(data_source, organization, image_name_3, image_url_3, make_image):
    return make_image(data_source, organization, image_name_3, image_url_3)


@pytest.fixture
def keyword(data_source, organization, kw_name, make_keyword):
    return make_keyword(data_source, organization, kw_name)


@pytest.fixture
def keyword2(data_source, organization, kw_name_2, make_keyword):
    return make_keyword(data_source, organization, kw_name_2)


@pytest.fixture
def keyword3(data_source, organization, kw_name_3, make_keyword):
    return make_keyword(data_source, organization, kw_name_3)


@pytest.fixture(scope="class")
def make_keyword_id(make_keyword):
    def _make_keyword_id(data_source, organization, kw_name):
        obj = make_keyword(data_source, organization, kw_name)
        obj_id = reverse(KeywordSerializer.view_name, kwargs={"pk": obj.id})
        return obj_id

    return _make_keyword_id


@pytest.fixture
def keyword_id(data_source, organization, kw_name, make_keyword_id):
    return make_keyword_id(data_source, organization, kw_name)


@pytest.fixture(scope="class")
def make_keyword_set():
    def _make_keyword_set(data_source, organization, kw_set_name):
        return KeywordSet.objects.create(
            id=data_source.id + ":" + kw_set_name,
            name=kw_set_name,
            organization=organization,
            data_source=data_source,
        )

    return _make_keyword_set


@pytest.fixture
def keyword_set_dict(data_source, organization):
    return {
        "id": data_source.id + ":testi-12345",
        "data_source": data_source.id,
        "organization": organization.id,
        "usage": "audience",
        "name": {
            "fi": "Testi avainsanaryhmä",
            "en": "Test keyword set",
        },
    }


@pytest.fixture
def keyword_set(
    make_keyword_set, data_source, keyword, keyword2, organization, kw_name_set
):
    kw_set = make_keyword_set(data_source, organization, kw_name_set)
    kw_set.keywords.set([keyword, keyword2])
    return kw_set


@pytest.fixture
def keyword_set2(
    make_keyword_set, other_data_source, keyword3, organization, kw_name_set_2
):
    kw_set = make_keyword_set(other_data_source, organization, kw_name_set_2)
    kw_set.keywords.set([keyword3])
    return kw_set


@pytest.fixture
def languages():
    lang_objs = [
        Language.objects.get_or_create(id=lang)[0] for lang in ["fi", "sv", "en"]
    ]
    for lang in lang_objs:
        lang.service_language = True
        lang.save()

    return lang_objs


@pytest.fixture
def keywordlabel(kw_name, languages):
    return KeywordLabel.objects.create(name=kw_name, language=languages[0])


@pytest.fixture(scope="class")
def languages_class(request):
    lang_objs = [
        Language.objects.get_or_create(id=lang)[0] for lang in ["fi", "sv", "en"]
    ]
    request.cls.languages = lang_objs


def language_id(language):
    obj_id = reverse(LanguageSerializer.view_name, kwargs={"pk": language.pk})
    return obj_id


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


@pytest.fixture
def complex_event_dict(
    data_source, organization, location_id, languages, make_complex_event_dict
):
    return make_complex_event_dict(data_source, organization, location_id, languages)


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
    from .test_event_get import get_list

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
    from .test_event_get import get_list

    def f():
        return get_list(api_client, version)

    return f


@pytest.fixture
def registration(event, user):
    return Registration.objects.create(
        event=event,
        created_by=user,
        last_modified_by=user,
        enrolment_start_time=localtime(),
        enrolment_end_time=localtime() + timedelta(days=10),
        maximum_attendee_capacity=20,
        waiting_list_capacity=20,
    )


@pytest.fixture
def registration2(event2, user2):
    return Registration.objects.create(
        event=event2,
        created_by=user2,
        last_modified_by=user2,
        enrolment_start_time=localtime(),
        enrolment_end_time=localtime() + timedelta(days=10),
        maximum_attendee_capacity=20,
        waiting_list_capacity=20,
    )


@pytest.fixture
def registration3(event3, user):
    return Registration.objects.create(
        event=event3,
        created_by=user,
        last_modified_by=user,
        waiting_list_capacity=20,
    )


@pytest.fixture
def registration4(event4, user):
    return Registration.objects.create(
        event=event4,
        audience_min_age=6,
        audience_max_age=18,
        created_by=user,
        last_modified_by=user,
        waiting_list_capacity=20,
    )


@pytest.fixture
def user2_with_user_type(organization, user2, request):
    user_type = request.param
    if user_type == "org_regular":
        organization.regular_users.add(user2)

    elif user_type == "org_admin":
        organization.admin_users.add(user2)

    elif user_type == "org_registration_admin":
        organization.registration_admin_users.add(user2)

    elif user_type == "org_financial_admin":
        organization.financial_admin_users.add(user2)

    elif user_type == "staff":
        user2.is_staff = True
        user2.save()

    elif user_type == "admin":
        user2.is_staff = True
        user2.is_admin = True
        user2.save()

    elif user_type == "superuser":
        user2.is_staff = True
        user2.is_admin = True
        user2.is_superuser = True
        user2.save()

    elif user_type is None:
        pass

    else:
        raise ValueError("user_type was not handled in test")

    return user2
