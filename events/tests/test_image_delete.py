import os

import pytest
from resilient_logger.models import ResilientLogEntry
from rest_framework import status

from events.models import Image

from .test_event_images_v1 import create_uploaded_image
from .utils import versioned_reverse as reverse


def get_image_path(image):
    return image.image.path


def assert_create_image(organization, data_source):
    uploaded_image = create_uploaded_image()
    existing_image = Image.objects.create(
        data_source=data_source,
        image=uploaded_image,
        publisher=organization,
        license=None,
    )

    assert Image.objects.all().count() == 1
    # verify that the image file exists at first just in case
    image_path = get_image_path(existing_image)
    assert os.path.isfile(image_path)

    return existing_image


def delete_image(api_client, image):
    detail_url = reverse("image-detail", kwargs={"pk": image.pk})
    response = api_client.delete(detail_url)

    return response


def assert_delete_image(api_client, image):
    response = delete_image(api_client, image)

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db(transaction=True)  # transaction is needed for django-cleanup
def test__delete_an_image(api_client, data_source, user, organization):
    api_client.force_authenticate(user)

    existing_image = assert_create_image(organization, data_source)

    assert_delete_image(api_client, existing_image)
    assert Image.objects.all().count() == 0
    # check that the image file is deleted
    image_path = get_image_path(existing_image)
    assert not os.path.isfile(image_path)


@pytest.mark.django_db
def test_image_id_is_audit_logged_on_delete(user_api_client, image):
    assert_delete_image(user_api_client, image)

    audit_log_entry = ResilientLogEntry.objects.first()
    assert audit_log_entry.context["target"]["object_ids"] == [image.pk]


@pytest.mark.django_db
def test__unauthenticated_user_cannot_delete_image(api_client, image):
    response = delete_image(api_client, image)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__regular_user_cannot_delete_image(api_client, image, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    response = delete_image(api_client, image)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_from_other_organization_cannot_delete_image(
    api_client, image, organization2, user2
):
    organization2.admin_users.add(user2)
    api_client.force_authenticate(user2)

    response = delete_image(api_client, image)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__image_from_another_data_source_can_be_deleted_by_admin(
    api_client, image, user, organization, other_data_source
):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)

    image.data_source = other_data_source
    image.save()
    other_data_source.user_editable_resources = True
    other_data_source.owner = organization
    other_data_source.save()

    assert image.data_source == other_data_source
    assert other_data_source in organization.owned_systems.all()

    # user can still delete the image
    response = delete_image(api_client, image)
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test__non_user_editable_resources_cannot_delete_image(
    api_client, image, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save()
    api_client.force_authenticate(user)

    response = delete_image(api_client, image)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_editable_resources_can_delete_image(
    api_client, image, data_source, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user)

    response = delete_image(api_client, image)
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test__api_key_with_organization_can_delete_image(
    api_client, image, data_source, organization
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = delete_image(api_client, image)
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test__api_key_of_other_organization_cannot_delete_image(
    api_client, image, data_source, organization2
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = delete_image(api_client, image)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__api_key_from_wrong_data_source_cannot_update_image(
    api_client, image, organization, other_data_source
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    response = delete_image(api_client, image)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_delete_keywordset(api_client, image):
    api_client.credentials(apikey="unknown")

    response = delete_image(api_client, image)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
