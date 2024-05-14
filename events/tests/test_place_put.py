import pytest
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.auth import ApiKeyUser
from events.tests.test_place_post import create_with_post
from events.tests.utils import assert_place_data_is_equal

from .utils import versioned_reverse as reverse

# === util methods ===


def update_with_put(api_client, place_id, place_data, credentials=None):
    if credentials:
        api_client.credentials(**credentials)
    response = api_client.put(place_id, place_data, format="json")
    return response


# === tests ===


@pytest.mark.parametrize(
    "user2_with_user_type",
    ["org_admin", "superuser"],
    indirect=["user2_with_user_type"],
)
@pytest.mark.django_db
def test_update_a_place_with_put(api_client, place_dict, user2_with_user_type):
    # create a place
    api_client.force_authenticate(user2_with_user_type)
    response = create_with_post(api_client, place_dict)

    # set up updates
    data2 = response.data

    for key in ("name", "description", "street_address", "address_locality"):
        for lang in ("fi", "en"):
            if lang in data2[key]:
                data2[key][lang] = "%s updated" % data2[key][lang]

    place_id = data2.pop("@id")
    response2 = update_with_put(api_client, place_id, data2)
    # assert
    assert_place_data_is_equal(data2, response2.data)


@pytest.mark.django_db
def test_place_id_is_audit_logged_on_put(user_api_client, place, place_dict):
    detail_url = reverse("place-detail", kwargs={"pk": place.pk})

    response = update_with_put(user_api_client, detail_url, place_dict)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [place.pk]


@pytest.mark.django_db
def test_a_non_admin_cannot_update_a_place(api_client, place, place_dict, user):
    place.publisher.admin_users.remove(user)
    api_client.force_authenticate(user)

    detail_url = reverse("place-detail", kwargs={"pk": place.pk})
    response = update_with_put(api_client, detail_url, place_dict)
    assert response.status_code == 403


@pytest.mark.django_db
def test_an_admin_can_update_an_place_from_another_data_source(
    api_client, place2, other_data_source, organization, user
):
    other_data_source.owner = organization
    other_data_source.user_editable_resources = True
    other_data_source.save()
    place2.publisher = organization
    place2.name = {"en": "Test location - updated", "fi": "Testipaikka - updated"}
    place2.save()
    api_client.force_authenticate(user)

    detail_url = reverse("place-detail", kwargs={"pk": place2.pk})
    response = api_client.get(detail_url, format="json")
    assert response.status_code == 200
    response = update_with_put(api_client, detail_url, response.data)
    assert response.status_code == 200


@pytest.mark.django_db
def test_correct_api_key_can_update_a_place(
    api_client, place, place_dict, data_source, organization
):
    data_source.owner = organization
    data_source.save()

    detail_url = reverse("place-detail", kwargs={"pk": place.pk})
    response = update_with_put(
        api_client, detail_url, place_dict, credentials={"apikey": data_source.api_key}
    )
    assert response.status_code == 200
    assert ApiKeyUser.objects.all().count() == 1


@pytest.mark.django_db
def test_wrong_api_key_cannot_update_a_place(
    api_client, place, place_dict, data_source, other_data_source
):
    detail_url = reverse("place-detail", kwargs={"pk": place.pk})
    response = update_with_put(
        api_client,
        detail_url,
        place_dict,
        credentials={"apikey": other_data_source.api_key},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_api_key_without_organization_cannot_update_a_place(
    api_client, place, place_dict, data_source
):
    detail_url = reverse("place-detail", kwargs={"pk": place.pk})
    response = update_with_put(
        api_client, detail_url, place_dict, credentials={"apikey": data_source.api_key}
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_unknown_api_key_cannot_update_a_place(api_client, place, place_dict):
    detail_url = reverse("place-detail", kwargs={"pk": place.pk})
    response = update_with_put(
        api_client, detail_url, place_dict, credentials={"apikey": "unknown"}
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_empty_api_key_cannot_update_a_place(
    api_client,
    place,
    place_dict,
):
    detail_url = reverse("place-detail", kwargs={"pk": place.pk})
    response = update_with_put(
        api_client, detail_url, place_dict, credentials={"apikey": ""}
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_non_user_editable_resources_cannot_update_a_place(
    api_client, place, place_dict, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()
    api_client.force_authenticate(user=user)
    detail_url = reverse("place-detail", kwargs={"pk": place.pk})
    response = update_with_put(api_client, detail_url, place_dict)
    assert response.status_code == 403


@pytest.mark.django_db
def test_user_editable_resources_can_update_a_place(
    api_client, place, place_dict, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user=user)
    detail_url = reverse("place-detail", kwargs={"pk": place.pk})
    response = update_with_put(api_client, detail_url, place_dict)
    assert response.status_code == 200


@pytest.mark.django_db
def test_put_place_position(place, user, api_client):
    api_client.force_authenticate(user)
    detail_url = reverse("place-detail", kwargs={"pk": place.pk})
    payload = {
        "id": place.id,
        "name": {"fi": "Testi1 EDITED", "sv": "", "en": ""},
        "data_source": place.data_source.id,
        "publisher": place.publisher.id,
        "position": {"type": "Point", "coordinates": [25.01497, 60.250507]},
    }

    response = update_with_put(api_client, detail_url, payload)

    assert response.data["position"] == payload["position"]
