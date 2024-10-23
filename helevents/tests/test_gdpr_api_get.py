from typing import Optional
from uuid import UUID

import pytest
import requests_mock
from django.conf import settings
from django.db.models import Q, QuerySet
from django.test import override_settings
from django.urls import reverse
from django_orghierarchy.models import Organization
from helusers.settings import api_token_auth_settings
from rest_framework import status

from events.models import Event
from events.tests.conftest import APIClient
from events.tests.factories import (
    EventFactory,
    ImageFactory,
    KeywordFactory,
    KeywordLabelFactory,
    LanguageFactory,
    OfferFactory,
    OrganizationFactory,
    PlaceFactory,
    VideoFactory,
)
from helevents.models import User
from helevents.tests.conftest import get_api_token_for_user_with_scopes
from helevents.tests.factories import UserFactory
from registrations.models import SignUp, SignUpContactPerson, SignUpGroup
from registrations.notifications import NotificationType
from registrations.tests.factories import (
    RegistrationFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpProtectedDataFactory,
)

TRANSLATION_LANGUAGES = sorted(
    [
        "sv",
        "ar",
        "zh_hans",
        "fi",
        "en",
        "ru",
    ]
)


# === util methods ===


def _get_contact_person_data(contact_person: SignUpContactPerson) -> dict:
    return {
        "key": "SIGNUPCONTACTPERSON",
        "children": [
            {"key": "ID", "value": contact_person.id},
            {"key": "FIRST_NAME", "value": contact_person.first_name},
            {"key": "LAST_NAME", "value": contact_person.last_name},
            {"key": "EMAIL", "value": contact_person.email},
            {"key": "PHONE_NUMBER", "value": contact_person.phone_number},
            {
                "key": "NATIVE_LANGUAGE",
                "value": str(contact_person.native_language),
            },
            {
                "key": "SERVICE_LANGUAGE",
                "value": str(contact_person.service_language),
            },
            {
                "key": "MEMBERSHIP_NUMBER",
                "value": contact_person.membership_number,
            },
            {
                "key": "NOTIFICATIONS",
                "value": str(contact_person.get_notifications_display()),
            },
        ],
    }


def _get_signup_group_profile_data(signup_group: Optional[SignUpGroup]) -> dict:
    if not signup_group:
        return {"key": "SIGNUP_GROUP", "value": None}

    profile_data = {
        "key": "SIGNUPGROUP",
        "children": [
            {"key": "ID", "value": signup_group.id},
            {"key": "REGISTRATION_ID", "value": signup_group.registration_id},
            {"key": "EXTRA_INFO", "value": signup_group.extra_info},
            {"key": "SIGNUPS_COUNT", "value": signup_group.signups.count()},
        ],
    }

    contact_person = getattr(signup_group, "contact_person", None)
    if not contact_person:
        return profile_data

    profile_data["children"].append(_get_contact_person_data(contact_person))
    return profile_data


def _get_field_translations(obj: object, field_name: str) -> list:
    return [
        {
            "key": f"{field_name}_{lang}".upper(),
            "value": getattr(obj, f"{field_name}_{lang}"),
        }
        for lang in TRANSLATION_LANGUAGES
        if getattr(obj, f"{field_name}_{lang}", False)
    ]


def _get_event_data(user) -> list:
    events = Event.objects.filter(created_by=user)

    event_data = []
    for e in events:
        image = e.images.first()
        keyword = e.keywords.first()
        keyword_label = keyword.alt_labels.first() if keyword else None
        language = e.in_language.first()
        offer = e.offers.first()
        video = e.videos.first()
        audience = e.audience.first()
        audience_label = audience.alt_labels.first() if audience else None

        data = {
            "children": [
                {"key": "ID", "value": e.id},
                {"key": "NAME", "children": _get_field_translations(e, "name")},
                {
                    "key": "DESCRIPTION",
                    "children": _get_field_translations(e, "description"),
                },
                {
                    "key": "SHORT_DESCRIPTION",
                    "children": _get_field_translations(e, "short_description"),
                },
                {"key": "START_TIME", "value": e.start_time},
                {"key": "END_TIME", "value": e.end_time},
                (
                    [
                        {
                            "children": (
                                [
                                    {"key": "NAME", "value": image.name},
                                    {"key": "URL", "value": image.url},
                                ]
                                if image
                                else []
                            ),
                            "key": "IMAGE",
                        }
                    ]
                    if image
                    else []
                ),
                (
                    [
                        {
                            "children": [
                                [
                                    {
                                        "children": (
                                            [
                                                {
                                                    "key": "NAME",
                                                    "value": keyword_label.name,
                                                },
                                                {
                                                    "children": [
                                                        {
                                                            "key": "NAME",
                                                            "children": _get_field_translations(
                                                                keyword_label.language,
                                                                "name",
                                                            ),
                                                        },
                                                        {
                                                            "key": "SERVICE_LANGUAGE",
                                                            "value": keyword_label.language.service_language,
                                                        },
                                                    ],
                                                    "key": "LANGUAGE",
                                                },
                                            ]
                                            if keyword_label
                                            else []
                                        ),
                                        "key": "KEYWORDLABEL",
                                    }
                                ]
                            ],
                            "key": "KEYWORD",
                        }
                    ]
                    if keyword
                    else []
                ),
                {
                    "key": "PUBLISHER",
                    "value": f"{e.publisher.id} - {e.publisher.name}",
                },
                (
                    [
                        {
                            "children": (
                                [
                                    {
                                        "key": "NAME",
                                        "children": _get_field_translations(
                                            language, "name"
                                        ),
                                    },
                                    {
                                        "key": "SERVICE_LANGUAGE",
                                        "value": language.service_language,
                                    },
                                ]
                                if language
                                else []
                            ),
                            "key": "LANGUAGE",
                        }
                    ]
                    if language
                    else []
                ),
                (
                    {
                        "children": [
                            {
                                "key": "NAME",
                                "children": _get_field_translations(e.location, "name"),
                            },
                            {
                                "key": "PUBLISHER",
                                "value": f"{e.location.publisher.id} - {e.location.publisher.name}",
                            },
                            {
                                "key": "INFO_URL",
                                "children": _get_field_translations(
                                    e.location, "info_url"
                                ),
                            },
                            {
                                "key": "DESCRIPTION",
                                "children": _get_field_translations(
                                    e.location, "description"
                                ),
                            },
                            {"key": "EMAIL", "value": e.location.email},
                            {
                                "key": "TELEPHONE",
                                "children": _get_field_translations(
                                    e.location, "telephone"
                                ),
                            },
                            {
                                "key": "STREET_ADDRESS",
                                "children": _get_field_translations(
                                    e.location, "street_address"
                                ),
                            },
                            {
                                "key": "ADDRESS_LOCALITY",
                                "children": _get_field_translations(
                                    e.location, "address_locality"
                                ),
                            },
                            {
                                "key": "ADDRESS_REGION",
                                "value": e.location.address_region,
                            },
                            {"key": "POSTAL_CODE", "value": e.location.postal_code},
                            {
                                "key": "POST_OFFICE_BOX_NUM",
                                "value": e.location.post_office_box_num,
                            },
                            {
                                "key": "ADDRESS_COUNTRY",
                                "value": e.location.address_country,
                            },
                        ],
                        "key": "PLACE",
                    }
                    if e.location
                    else {"key": "LOCATION", "value": None}
                ),
                {
                    "children": (
                        [
                            {
                                "children": [
                                    {
                                        "key": "PRICE",
                                        "children": _get_field_translations(
                                            offer, "price"
                                        ),
                                    },
                                    {
                                        "key": "DESCRIPTION",
                                        "children": _get_field_translations(
                                            offer, "description"
                                        ),
                                    },
                                ],
                                "key": "OFFER",
                            }
                        ]
                        if offer
                        else []
                    ),
                    "key": "OFFERS",
                },
                {
                    "children": (
                        [
                            {
                                "children": [
                                    {"key": "NAME", "value": video.name},
                                    {"key": "URL", "value": video.url},
                                    {"key": "ALT_TEXT", "value": video.alt_text},
                                ],
                                "key": "VIDEO",
                            }
                        ]
                        if video
                        else []
                    ),
                    "key": "VIDEOS",
                },
                (
                    [
                        {
                            "children": (
                                [
                                    [
                                        {
                                            "children": [
                                                {
                                                    "key": "NAME",
                                                    "value": audience_label.name,
                                                },
                                                {
                                                    "children": [
                                                        {
                                                            "key": "NAME",
                                                            "children": _get_field_translations(
                                                                language, "name"
                                                            ),
                                                        },
                                                        {
                                                            "key": "SERVICE_LANGUAGE",
                                                            "value": audience_label.language.service_language,
                                                        },
                                                    ],
                                                    "key": "LANGUAGE",
                                                },
                                            ],
                                            "key": "KEYWORDLABEL",
                                        }
                                    ]
                                ]
                                if audience
                                else []
                            ),
                            "key": "KEYWORD",
                        }
                    ]
                    if audience
                    else []
                ),
                {"key": "INFO_URL", "children": _get_field_translations(e, "info_url")},
            ],
            "key": "EVENT",
        }
        if e.user_email == user.email:
            data["children"].extend(
                [
                    {
                        "key": "USER_EMAIL",
                        "value": e.user_email,
                    },
                    {"key": "USER_NAME", "value": e.user_name},
                    {
                        "key": "USER_PHONE_NUMBER",
                        "value": e.user_phone_number,
                    },
                    {
                        "key": "USER_ORGANIZATION",
                        "value": e.user_organization,
                    },
                    {
                        "key": "USER_CONSENT",
                        "value": e.user_consent,
                    },
                ]
            )

        event_data.append(data)

    return event_data


def _get_organizations(user: User) -> list[dict]:
    orgs = []

    for org in Organization.objects.filter(Q(admin_users=user) | Q(regular_users=user)):
        orgs.append(
            {
                "children": [
                    {"key": "ID", "value": org.id},
                    {"key": "NAME", "value": org.name},
                ],
                "key": "SERIALIZABLEPUBLISHER",
            }
        )

    return orgs


def _get_signup_profile_data(signup: SignUp) -> dict:
    profile_data = {
        "key": "SIGNUP",
        "children": [
            {"key": "FIRST_NAME", "value": signup.first_name},
            {"key": "LAST_NAME", "value": signup.last_name},
            {
                "key": "DATE_OF_BIRTH",
                "value": (
                    signup.date_of_birth.strftime("%Y-%m-%d")
                    if signup.date_of_birth
                    else None
                ),
            },
            {"key": "PHONE_NUMBER", "value": signup.phone_number},
            {"key": "CITY", "value": signup.city},
            {"key": "STREET_ADDRESS", "value": signup.street_address},
            {"key": "ZIPCODE", "value": signup.zipcode},
            {"key": "REGISTRATION_ID", "value": signup.registration_id},
            _get_signup_group_profile_data(signup.signup_group),
            {"key": "EXTRA_INFO", "value": signup.extra_info},
            {
                "key": "ATTENDEE_STATUS",
                "value": dict(SignUp.ATTENDEE_STATUSES)[signup.attendee_status],
            },
            {
                "key": "PRESENCE_STATUS",
                "value": dict(SignUp.PRESENCE_STATUSES)[signup.presence_status],
            },
            {"key": "USER_CONSENT", "value": signup.user_consent},
        ],
    }

    contact_person = getattr(signup, "contact_person", None)
    if not contact_person:
        return profile_data

    profile_data["children"].append(_get_contact_person_data(contact_person))
    return profile_data


def _get_signups_profile_data(signups_qs: QuerySet[SignUp]) -> list[dict]:
    signup_datas = []

    for signup in signups_qs:
        signup_data = _get_signup_profile_data(signup)
        signup_datas.append(signup_data)

    return signup_datas


def _get_user_data(user: User, expect_event_user_data: bool = True) -> list[dict]:
    Event.objects.filter(
        user_email=user.email, publisher=settings.EXTERNAL_USER_PUBLISHER_ID
    ).first()

    return [
        {"key": "ID", "value": user.id},
        {"key": "FIRST_NAME", "value": user.first_name},
        {"key": "LAST_NAME", "value": user.last_name},
        {"key": "EMAIL", "value": user.email},
        {
            "key": "SIGNUP_CREATED_BY",
            "children": _get_signups_profile_data(
                user.signup_created_by.select_related("signup_group").all()
            ),
        },
        {
            "key": "EVENTS_EVENT_CREATED_BY",
            "children": _get_event_data(user),
        },
        {"key": "PUBLISHER_ORGANIZATIONS", "value": _get_organizations(user)},
    ]


def _get_gdpr_data(api_client: APIClient, user_uuid: UUID):
    gdpr_profile_url = reverse("helsinki_gdpr:gdpr_v1", kwargs={"uuid": user_uuid})
    return api_client.get(gdpr_profile_url)


def _assert_profile_data_in_response(response, user: User):
    profile_data = {"key": "USER", "children": _get_user_data(user)}
    assert response.json() == profile_data


# === tests ===


@pytest.mark.parametrize("use_contact_person", [True, False])
@override_settings(EXTERNAL_USER_PUBLISHER_ID="ext-org")
@pytest.mark.django_db
def test_authenticated_user_can_get_own_data(api_client, settings, use_contact_person):
    settings.GDPR_API_QUERY_SCOPE = api_token_auth_settings.API_SCOPE_PREFIX

    user = UserFactory(email="also_an_exteral_user@localhost")

    language_en = LanguageFactory(id="en", name="English")
    language_fi = LanguageFactory(id="fi", name="Suomi", service_language=True)

    EventFactory.create_batch(5, created_by=UserFactory(), name="someoneelsesevent")
    org = OrganizationFactory(name="admin_org")
    regular_org = OrganizationFactory(name="regular_org")
    OrganizationFactory(name="im_not_included_org")
    org.admin_users.add(user)
    regular_org.regular_users.add(user)

    event = EventFactory(
        created_by=user,
        publisher=org,
        user_organization=org.name,
        location=PlaceFactory(
            name="Test place",
            info_url="https://localhost/place",
            description="Test place",
            email="place@localhost",
            telephone="+123123123",
            street_address="Test Street 1",
            address_region="Test Region",
            address_locality="Test Locality",
            postal_code="12345",
            post_office_box_num="123",
            address_country="XG",
        ),
        info_url="https://localhost/event",
    )
    OfferFactory(price="10", description="Test offer", event=event)
    VideoFactory(
        name="test_video",
        url="https://localhost/video",
        alt_text="Test video",
        event=event,
    )

    keyword = KeywordFactory(name="test_keyword")
    keyword.alt_labels.add(
        KeywordLabelFactory(name="test_keyword label", language=language_en)
    )
    audience = KeywordFactory(name="test_audience")
    audience.alt_labels.add(
        KeywordLabelFactory(name="test_audience label", language=language_en)
    )

    event.audience.add(audience)
    event.keywords.add(keyword)
    event.in_language.add(language_en)
    event.images.add(ImageFactory(name="test image", url="https://localhost/image"))

    ext_org = OrganizationFactory(id="ext-org", name="External org")
    EventFactory(
        created_by=user,
        publisher=ext_org,
        info_url="https://localhost/extevent",
        user_email=user.email,
        user_name="ext_user",
        user_phone_number="+123123123",
        user_organization="ext-org",
        user_consent=True,
    )

    registration = RegistrationFactory(event=event)

    signup_group = SignUpGroupFactory(registration=registration, created_by=user)

    first_signup = SignUpFactory(
        registration=registration,
        signup_group=signup_group,
        first_name="Mickey",
        last_name="Mouse",
        phone_number="044111111",
        city="Test City",
        street_address="Test Street 1",
        zipcode="12345",
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
        presence_status=SignUp.PresenceStatus.PRESENT,
        created_by=user,
    )
    SignUpProtectedDataFactory(
        registration=registration,
        signup=first_signup,
        date_of_birth="1928-05-15",
        extra_info="Test extra info #1",
    )

    second_signup = SignUpFactory(
        registration=registration,
        first_name="James",
        last_name="Bond",
        phone_number="040111111",
        city="Test City #2",
        street_address="Test Street 2",
        zipcode="12121",
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        presence_status=SignUp.PresenceStatus.NOT_PRESENT,
        user_consent=True,
        created_by=user,
    )
    SignUpProtectedDataFactory(
        registration=registration,
        signup=second_signup,
        date_of_birth="1920-11-11",
        extra_info="Test extra info #2",
    )

    if use_contact_person:
        SignUpContactPersonFactory(
            signup_group=signup_group,
            first_name="Mickey",
            last_name="Mouse",
            email="test@test.com",
            phone_number="+123123456789",
            native_language=language_en,
            service_language=language_fi,
            membership_number="00000",
            notifications=NotificationType.EMAIL,
        )

        SignUpContactPersonFactory(
            signup=second_signup,
            first_name="James",
            last_name="Bond",
            email="test007@test.com",
            phone_number="+123000111222",
            native_language=language_en,
            service_language=language_en,
            membership_number="00001",
            notifications=NotificationType.SMS,
        )

    with requests_mock.Mocker() as req_mock:
        auth_header = get_api_token_for_user_with_scopes(
            user.uuid, [settings.GDPR_API_QUERY_SCOPE], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)

        response = _get_gdpr_data(api_client, user.uuid)
        assert response.status_code == status.HTTP_200_OK

    _assert_profile_data_in_response(response, user)


@pytest.mark.django_db
def test_authenticated_user_cannot_get_other_users_data(api_client, settings):
    user = UserFactory()
    other_user = UserFactory()

    with requests_mock.Mocker() as req_mock:
        auth_header = get_api_token_for_user_with_scopes(
            user.uuid, [settings.GDPR_API_QUERY_SCOPE], req_mock
        )
        api_client.credentials(HTTP_AUTHORIZATION=auth_header)

        response = _get_gdpr_data(api_client, other_user.uuid)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_non_authenticated_user_cannot_get_any_data(api_client, settings):
    user = UserFactory()

    response = _get_gdpr_data(api_client, user.uuid)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
