import math
from collections import Counter
from typing import Optional, Union

import pytest
from django.utils import translation
from rest_framework import status
from rest_framework.test import APIClient

from audit_log.models import AuditLogEntry
from events.tests.utils import assert_fields_exist
from events.tests.utils import versioned_reverse as reverse
from registrations.models import PriceGroup
from registrations.tests.factories import PriceGroupFactory
from registrations.tests.utils import create_user_by_role

# === util methods ===


def get_detail(api_client: APIClient, price_group_pk: Union[str, int]):
    url = reverse(
        "pricegroup-detail",
        kwargs={"pk": price_group_pk},
    )

    return api_client.get(url)


def get_list(api_client: APIClient, query: Optional[str] = None, data=None):
    url = reverse("pricegroup-list")

    if query:
        url = "%s?%s" % (url, query)

    return api_client.get(url, data=data)


def assert_get_detail(api_client: APIClient, price_group_pk: Union[str, int]):
    response = get_detail(api_client, price_group_pk)
    assert response.status_code == status.HTTP_200_OK

    return response


def assert_get_list(api_client: APIClient, query: Optional[str] = None):
    response = get_list(api_client, query=query)
    assert response.status_code == status.HTTP_200_OK

    return response


def assert_price_group_fields_exist(data):
    fields = (
        "id",
        "created_time",
        "last_modified_time",
        "created_by",
        "last_modified_by",
        "publisher",
        "description",
        "is_free",
    )
    assert_fields_exist(data, fields)


# === tests ===


@pytest.mark.parametrize(
    "user_role",
    [
        "superuser",
        "admin",
        "registration_admin",
        "financial_admin",
        "regular_user",
    ],
)
@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_authenticated_user_can_get_price_group_detail_and_list(
    api_client, organization, user_role, url_type
):
    price_group = PriceGroupFactory(
        publisher=organization,
        description_fi="FI",
        description_sv="SV",
        description_en="EN",
    )

    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    if url_type == "list":
        response = assert_get_list(api_client)
        assert (
            len(response.data["data"]) == 9
        )  # eight default groups + one created in this test
    else:
        response = assert_get_detail(api_client, price_group.pk)
        assert_price_group_fields_exist(response.data)
        assert_fields_exist(response.data["description"], ("fi", "sv", "en"))


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_anonymous_user_cannot_get_price_group_detail_or_list(
    api_client, organization, url_type
):
    price_group = PriceGroupFactory(publisher=organization)

    if url_type == "list":
        PriceGroupFactory(publisher=organization)
        response = get_list(api_client)
    else:
        response = get_detail(api_client, price_group.pk)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("url_type", ["detail", "list"])
@pytest.mark.django_db
def test_apikey_user_can_get_price_group_detail_and_list(
    api_client, organization, data_source, url_type
):
    price_group = PriceGroupFactory(publisher=organization)

    data_source.owner = organization
    data_source.save(update_fields=["owner"])

    api_client.credentials(apikey=data_source.api_key)

    if url_type == "list":
        response = assert_get_list(api_client)
        assert (
            len(response.data["data"]) == 9
        )  # eight default groups + one created in this test
    else:
        response = assert_get_detail(api_client, price_group.pk)
        assert_price_group_fields_exist(response.data)


@pytest.mark.parametrize("user_role", ["superuser", "financial_admin"])
@pytest.mark.django_db
def test_filter_price_groups_by_publisher(
    api_client, organization, organization2, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    price_group = PriceGroupFactory(publisher=organization)
    price_group2 = PriceGroupFactory(publisher=organization)

    price_group3 = PriceGroupFactory(publisher=organization2)

    response = assert_get_list(api_client, query="publisher=None")
    assert len(response.data["data"]) == 8  # eight default groups
    assert Counter(
        list(PriceGroup.objects.filter(publisher=None).values_list("pk", flat=True))
    ) == Counter([group["id"] for group in response.data["data"]])

    response = assert_get_list(api_client, query=f"publisher={organization2.pk}")
    assert len(response.data["data"]) == 1
    assert response.data["data"][0]["id"] == price_group3.pk

    response = assert_get_list(api_client, query=f"publisher={organization.pk}")
    assert len(response.data["data"]) == 2
    assert Counter([price_group.pk, price_group2.pk]) == Counter(
        [group["id"] for group in response.data["data"]]
    )

    response = assert_get_list(
        api_client, query=f"publisher={organization.pk},{organization2.pk}"
    )
    assert len(response.data["data"]) == 3
    assert Counter([price_group.pk, price_group2.pk, price_group3.pk]) == Counter(
        [group["id"] for group in response.data["data"]]
    )


@pytest.mark.django_db
def test_filter_price_groups_by_publisher_without_publishers(api_client):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    response = assert_get_list(api_client, query="publisher=1")
    assert len(response.data["data"]) == 0

    response = assert_get_list(api_client, query="publisher=none")
    assert len(response.data["data"]) == 8  # default price groups found


@pytest.mark.parametrize(
    "lang,query_term,expected_description",
    [
        ("en", "Adult", "Adult"),
        ("fi", "Aikuinen", "Aikuinen"),
        ("sv", "Vuxen", "Vuxen"),
        ("en", "pensio", "Pensioner"),
        ("fi", "eläk", "Eläkeläinen"),
        ("sv", "pensio", "Pensionär"),
    ],
)
@pytest.mark.django_db
def test_filter_price_groups_by_description(
    api_client, lang, query_term, expected_description
):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    with translation.override(lang):
        response = assert_get_list(api_client, query=f"description={query_term}")
    assert len(response.data["data"]) == 1
    assert response.data["data"][0]["description"][lang] == expected_description


@pytest.mark.parametrize(
    "is_free,expected_count",
    [
        (1, 2),
        (0, 6),
    ],
)
@pytest.mark.django_db
def test_filter_by_is_free(api_client, is_free, expected_count):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    price_groups = PriceGroup.objects.filter(publisher=None, is_free=bool(is_free))
    assert price_groups.count() == expected_count

    response = assert_get_list(api_client, query=f"is_free={is_free}")
    assert len(response.data["data"]) == expected_count
    assert Counter(price_groups.values_list("pk", flat=True)) == Counter(
        [data["id"] for data in response.data["data"]]
    )


@pytest.mark.django_db
def test_price_group_list_ordering(api_client):
    PriceGroup.objects.filter(publisher=None).delete()

    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    price_groups = [
        PriceGroupFactory(description_fi=""),
        PriceGroupFactory(description_fi="1"),
        PriceGroupFactory(description_fi="2"),
        PriceGroupFactory(description_fi="Abc"),
        PriceGroupFactory(description_fi="Bcd"),
        PriceGroupFactory(description_fi="Cde"),
        PriceGroupFactory(description_fi="Dce"),
        PriceGroupFactory(description_fi="Äää"),
        PriceGroupFactory(description_fi="Äöö"),
        PriceGroupFactory(description_fi="Öää"),
        PriceGroupFactory(description_fi="Ööö"),
    ]

    # Sanity check for correct translations (use the first object with a non-empty
    # description; an empty value is replaced with a fallback value)
    with translation.override("fi"):
        assert price_groups[1].description == "1"

    page_size = 3
    page_count = math.ceil(len(price_groups) / page_size)
    for page in range(1, page_count + 1):
        # Price groups are ordered by description, so need to activate the correct
        # language.
        with translation.override("fi"):
            response = get_list(api_client, data={"page": page, "page_size": page_size})
        assert response.status_code == status.HTTP_200_OK, (
            f"expected status code 200 at page {page}, got {response.status_code} instead"
        )

        price_group_ids = [item["id"] for item in response.data["data"]]
        start = page_size * (page - 1)
        end = page_size * page
        expected_ids = [price_group.id for price_group in price_groups[start:end]]
        assert price_group_ids == expected_ids, (
            f"expected ids {expected_ids} at page {page}, got {price_group_ids} instead"
        )


@pytest.mark.django_db
def test_price_group_id_is_audit_logged_on_get_detail(api_client):
    price_group = PriceGroup.objects.filter(publisher=None).first()

    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    assert_get_detail(api_client, price_group.pk)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        price_group.pk
    ]


@pytest.mark.django_db
def test_price_group_ids_are_audit_logged_on_get_list(api_client):
    user = create_user_by_role("superuser", None)
    api_client.force_authenticate(user)

    assert_get_list(api_client)

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter(PriceGroup.objects.filter(publisher=None).values_list("pk", flat=True))
