from decimal import Decimal

import pytest
from resilient_logger.models import ResilientLogEntry
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from registrations.models import PriceGroup, Registration, RegistrationPriceGroup
from registrations.tests.factories import PriceGroupFactory
from registrations.tests.utils import create_user_by_role


def delete_registration(api_client, id):
    delete_url = reverse("registration-detail", kwargs={"pk": id})
    return api_client.delete(delete_url)


def assert_delete_registration(
    api_client, registration_pk: int, registrations_count: int = 1
):
    assert Registration.objects.count() == registrations_count

    response = delete_registration(api_client, registration_pk)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert Registration.objects.count() == registrations_count - 1


@pytest.mark.django_db
def test_delete_registration(api_client, registration, user):
    api_client.force_authenticate(user)
    assert_delete_registration(api_client, registration.pk)


@pytest.mark.django_db
def test_unauthenticated_user_cannot_delete_registration(api_client, registration):
    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_registration_with_signups_cannot_be_deleted(
    api_client, registration, signup, user
):
    api_client.force_authenticate(user)
    response = delete_registration(api_client, registration.id)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == "Registration with signups cannot be deleted"


@pytest.mark.parametrize("user_role", ["financial_admin", "regular_user"])
@pytest.mark.django_db
def test_not_allowed_user_roles_cannot_delete_registration(
    api_client, registration, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.parametrize("user_role", ["admin", "registration_admin"])
@pytest.mark.django_db
def test_admin_and_registration_admin_can_delete_registration_regardless_of_user_editable_resources(
    api_client,
    data_source,
    organization,
    registration,
    user_editable_resources,
    user_role,
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    assert_delete_registration(api_client, registration.pk)


@pytest.mark.django_db
def test_api_key_with_organization_can_delete_registration(
    api_client, data_source, organization, registration
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    assert_delete_registration(api_client, registration.pk)


@pytest.mark.django_db
def test_api_key_of_other_organization_cannot_delete_registration(
    api_client, data_source, organization2, registration
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_from_wrong_data_source_cannot_delete_registration(
    api_client, organization, other_data_source, registration
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_unknown_api_key_cannot_delete_registration(api_client, registration):
    api_client.credentials(apikey="unknown")

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_registration_id_is_audit_logged_on_delete(user_api_client, registration):
    response = delete_registration(user_api_client, registration.id)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    audit_log_entry = ResilientLogEntry.objects.first()
    assert audit_log_entry.context["target"]["object_ids"] == [registration.pk]


@pytest.mark.django_db
def test_delete_registration_and_price_groups(api_client, registration, user):
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(publisher=None).first()
    custom_price_group = PriceGroupFactory(publisher=registration.publisher)

    RegistrationPriceGroup.objects.create(
        registration=registration, price_group=default_price_group, price=Decimal("10")
    )
    RegistrationPriceGroup.objects.create(
        registration=registration, price_group=custom_price_group, price=Decimal("10")
    )

    assert RegistrationPriceGroup.objects.count() == 2

    response = delete_registration(api_client, registration.id)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert RegistrationPriceGroup.objects.count() == 0
