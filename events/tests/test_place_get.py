from collections import Counter

import pytest
from django.core.management import call_command
from pytest_django.asserts import assertNumQueries
from rest_framework import status
from rest_framework.exceptions import ValidationError

from audit_log.models import AuditLogEntry
from events.models import Place

from .test_event_get import get_detail as get_event_detail
from .utils import get
from .utils import versioned_reverse as reverse


def get_list(api_client, version="v1", data=None):
    list_url = reverse("place-list", version=version)
    return get(api_client, list_url, data=data)


def get_detail(api_client, detail_pk, version="v1", data=None):
    detail_url = reverse("place-detail", version=version, kwargs={"pk": detail_pk})
    return get(api_client, detail_url, data=data)


@pytest.mark.django_db
def test_get_place_detail(api_client, place):
    response = get_detail(api_client, place.pk)
    assert response.data["id"] == place.id


@pytest.mark.django_db
def test_place_id_is_audit_logged_on_get_detail(user_api_client, place):
    response = get_detail(user_api_client, place.pk)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [place.pk]


@pytest.mark.django_db
def test_place_id_is_audit_logged_on_get_list(user_api_client, place, place2):
    response = get_list(user_api_client, data={"show_all_places": True})
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter([place.pk, place2.pk])


@pytest.mark.django_db
def test_get_unknown_place_detail_check_404(api_client):
    response = api_client.get(reverse("place-detail", kwargs={"pk": "möö"}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_get_place_detail_check_redirect_and_event_remap(
    api_client, event, place, place2
):
    call_command("update_n_events")
    response = get_detail(api_client, place.pk)
    assert response.data["id"] == place.id
    assert response.data["n_events"] == 1
    event_response = get_event_detail(api_client, event.pk)
    assert event_response.data["location"]["@id"] == reverse(
        "place-detail", kwargs={"pk": place.id}
    )
    place.replaced_by = place2
    place.deleted = True
    place.save()
    call_command("update_n_events")
    url = reverse("place-detail", version="v1", kwargs={"pk": place.pk})
    response = api_client.get(url, data=None, format="json")
    assert response.status_code == 301
    response2 = api_client.get(response.url, data=None, format="json")
    assert response2.data["id"] == place2.id
    assert response2.data["n_events"] == 1
    event_response2 = get_event_detail(api_client, event.pk)
    assert event_response2.data["location"]["@id"] == reverse(
        "place-detail", kwargs={"pk": place2.id}
    )
    with pytest.raises(ValidationError):
        place2.replaced_by = place
        place.save()


@pytest.mark.django_db
def test_get_place_detail_redirect_to_end_of_replace_chain(
    api_client, place, place2, place3
):
    place.replaced_by = place2
    place.deleted = True
    place.save()
    place2.replaced_by = place3
    place2.deleted = True
    place2.save()
    url = reverse("place-detail", version="v1", kwargs={"pk": place.pk})
    response = api_client.get(url, data=None, format="json")
    assert response.status_code == 301
    response2 = api_client.get(response.url, data=None, format="json")
    assert response2.data["id"] == place3.id


@pytest.mark.django_db
def test_get_place_list_verify_text_filter(api_client, place, place2, place3):
    response = api_client.get(
        reverse("place-list"), data={"text": "Paikka", "show_all_places": True}
    )
    assert place.id in [entry["id"] for entry in response.data["data"]]
    assert place2.id not in [entry["id"] for entry in response.data["data"]]
    assert place3.id not in [entry["id"] for entry in response.data["data"]]


@pytest.mark.django_db
def test_get_place_list_verify_division_filter(
    api_client, place, place2, place3, administrative_division, administrative_division2
):
    place.divisions.set([administrative_division])
    place2.divisions.set([administrative_division2])
    place3.divisions.clear()

    # filter using one value
    response = get_list(
        api_client,
        data={"show_all_places": 1, "division": administrative_division.ocd_id},
    )
    data = response.data["data"]
    assert len(data) == 1
    assert place.id in [entry["id"] for entry in data]

    # filter using two values
    filter_value = "%s,%s" % (
        administrative_division.ocd_id,
        administrative_division2.ocd_id,
    )
    response = get_list(
        api_client, data={"show_all_places": 1, "division": filter_value}
    )
    data = response.data["data"]
    assert len(data) == 2
    ids = [entry["id"] for entry in data]
    assert place.id in ids
    assert place2.id in ids


@pytest.mark.django_db
def test_get_place_list_verify_show_deleted_filter(
    api_client, place, place2, administrative_division
):
    place.divisions.set([administrative_division])
    place2.divisions.set([administrative_division])
    place.deleted = True
    place.save()

    # Show both places
    response = get_list(
        api_client,
        data={
            "show_deleted": 1,
            "division": administrative_division.ocd_id,
            "show_all_places": 1,
        },
    )
    data = response.data["data"]
    assert len(data) == 2
    ids = [entry["id"] for entry in data]
    assert place.id in ids
    assert place2.id in ids

    # Don't include deleted place
    response = get_list(
        api_client,
        data={"division": administrative_division.ocd_id, "show_all_places": 1},
    )
    data = response.data["data"]
    assert len(data) == 1
    ids = [entry["id"] for entry in data]
    assert place.id not in ids
    assert place2.id in ids


@pytest.mark.django_db
def test_get_place_list_check_division(
    api_client, place, administrative_division, municipality
):
    place.divisions.set([administrative_division])

    response = get_list(api_client, data={"show_all_places": 1})
    division = response.data["data"][0]["divisions"][0]

    assert division["type"] == "neighborhood"
    assert division["name"] == {"en": "test division"}
    assert division["ocd_id"] == "ocd-division/test:1"
    assert division["municipality"] == "test municipality"


@pytest.mark.django_db
def test_get_place_with_upcoming_events(api_client, place, place2, event, past_event):
    event.location = place
    past_event.location = place2
    place.n_events = 1
    place2.n_events = 1

    event.save()
    past_event.save()
    place.save()
    place2.save()

    response = get_list(api_client, data={"has_upcoming_events": True})
    assert response.data["meta"]["count"] == 0

    Place.upcoming_events.has_upcoming_events_update()

    response = get_list(api_client, data={"has_upcoming_events": True})
    ids = [entry["id"] for entry in response.data["data"]]
    assert place.id in ids
    assert place2.id not in ids

    response = get_list(api_client, data={"has_upcoming_events": False})
    ids = [entry["id"] for entry in response.data["data"]]
    assert place.id in ids
    assert place2.id in ids


@pytest.mark.no_test_audit_log
@pytest.mark.django_db
def test_list_place_query_counts(api_client, place, place2, place3, settings):
    """
    Expect 7 queries when listing places
    1) COUNT
    2) SELECT places
    3) SELECT related publishers
    4) SELECT related division, join type and municipality
    5) SELECT related division municipality translations
    6) SELECT related division translations
    7) SELECT system data source
    """
    settings.AUDIT_LOG_ENABLED = False

    with assertNumQueries(7):
        get_list(api_client, data={"show_all_places": True})
