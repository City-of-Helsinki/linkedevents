from collections import Counter

import pytest
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.tests.utils import assert_fields_exist, get
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory


def get_list(api_client, version="v1"):
    list_url = reverse("user-list", version=version)
    return get(api_client, list_url)


def get_detail(api_client, detail_pk, version="v1"):
    detail_url = reverse("user-detail", version=version, kwargs={"pk": detail_pk})
    return get(api_client, detail_url)


def assert_user_fields_exist(data, version="v1"):
    # TODO: incorporate version parameter into version aware
    #  parts of test code
    fields = (
        "last_login",
        "username",
        "email",
        "date_joined",
        "first_name",
        "last_name",
        "uuid",
        "department_name",
        "organization",
        "is_staff",
        "is_superuser",
        "display_name",
        "admin_organizations",
        "registration_admin_organizations",
        "financial_admin_organizations",
        "organization_memberships",
        "is_external",
        "is_strongly_identified",
        "is_substitute_user",
    )
    assert_fields_exist(data, fields)


@pytest.mark.django_db
def test__get_user_detail(api_client, user, organization):
    api_client.force_authenticate(user=user)

    response = get_detail(api_client, user.pk)

    assert_user_fields_exist(response.data)


@pytest.mark.parametrize("is_admin", [True, False])
@pytest.mark.django_db
def test__get_user_list(api_client, user, organization, is_admin):
    if is_admin:
        user.is_superuser = True
        user.save()
    other_user = UserFactory()
    api_client.force_authenticate(user=user)

    response = get_list(api_client)

    data = response.data["data"]
    uuids = {u["uuid"] for u in data}
    if is_admin:
        assert len(data) == 2
        assert uuids == {str(user.uuid), str(other_user.uuid)}
    else:
        assert len(data) == 1
        assert uuids == {str(user.uuid)}


@pytest.mark.django_db
def test_user_id_is_audit_logged_on_get_detail(user_api_client, user):
    response = get_detail(user_api_client, user.pk)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [user.pk]


@pytest.mark.django_db
def test_user_id_is_audit_logged_on_get_list(api_client):
    user = UserFactory(is_superuser=True)
    api_client.force_authenticate(user)

    other_user = UserFactory()

    response = get_list(api_client)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter([user.pk, other_user.pk])
