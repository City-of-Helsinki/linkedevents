import pytest
from rest_framework import status

from audit_log.models import AuditLogEntry

from .utils import versioned_reverse as reverse


@pytest.mark.django_db
def test_place_delete(api_client, user, place):
    api_client.force_authenticate(user)

    response = api_client.delete(reverse("place-detail", kwargs={"pk": place.id}))
    assert response.status_code == 204

    response = api_client.get(reverse("place-detail", kwargs={"pk": place.id}))
    assert response.status_code == 410


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_delete_a_place(
    api_client, place, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()

    api_client.force_authenticate(user=user)

    response = api_client.delete(reverse("place-detail", kwargs={"pk": place.id}))
    assert response.status_code == 403


@pytest.mark.django_db
def test__user_editable_resources_can_delete_a_place(
    api_client, place, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()

    api_client.force_authenticate(user=user)

    response = api_client.delete(reverse("place-detail", kwargs={"pk": place.id}))
    assert response.status_code == 204

    response = api_client.get(reverse("place-detail", kwargs={"pk": place.id}))
    assert response.status_code == 410


@pytest.mark.django_db
def test_place_id_is_audit_logged_on_delete(user_api_client, place):
    response = user_api_client.delete(reverse("place-detail", kwargs={"pk": place.pk}))
    assert response.status_code == status.HTTP_204_NO_CONTENT

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [place.pk]
