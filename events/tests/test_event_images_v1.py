import random
from collections import Counter
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image as PILImage
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.auth import ApiKeyUser
from events.models import Image
from events.tests.test_event_put import update_with_put

from .test_event_post import create_with_post
from .utils import assert_event_data_is_equal, assert_fields_exist, get
from .utils import versioned_reverse as reverse

# === util methods ===


def create_in_memory_image_file(
    name="test_image", image_format="png", size=(512, 256), color=(128, 128, 128)
):
    image = PILImage.new("RGBA", size=size, color=color)
    file = BytesIO()
    file.name = "{}.{}".format(name, image_format)
    image.save(file, format=image_format)
    file.seek(0)
    return file


def create_uploaded_image(
    name="existing_test_image", file_name="existing_test_image.png"
):
    image_file = create_in_memory_image_file(name)
    return SimpleUploadedFile(
        file_name,
        image_file.read(),
        "image/png",
    )


def get_list(api_client):
    list_url = reverse("image-list")
    return get(api_client, list_url)


def get_detail(api_client, detail_pk):
    detail_url = reverse("image-detail", kwargs={"pk": detail_pk})
    return get(api_client, detail_url)


def assert_image_fields_exist(data, version="v1"):
    # TODO: start using version parameter
    fields = (
        "@context",
        "@id",
        "@type",
        "name",
        "publisher",
        "created_time",
        "cropping",
        "id",
        "has_user_editable_resources",
        "url",
        "last_modified_time",
        "license",
        "photographer_name",
        "data_source",
        "alt_text",
        "license_url",
    )

    assert_fields_exist(data, fields)


# === fixtures ===


@pytest.fixture(autouse=True)
def setup(settings):
    settings.EXTERNAL_USER_PUBLISHER_ID = "others"
    settings.ENABLE_EXTERNAL_USER_EVENTS = True


@pytest.fixture
def list_url():
    return reverse("image-list")


@pytest.fixture
def image_data():
    image_file = create_in_memory_image_file()
    return {
        "image": image_file,
    }


@pytest.fixture
def image_url():
    url = "https://commons.wikimedia.org/wiki/File:Common_Squirrel.jpg"
    return {
        "url": url,
    }


# === tests ===


@pytest.mark.django_db
def test_get_image_list_check_fields_exist(api_client):
    uploaded_image = create_uploaded_image()
    Image.objects.create(image=uploaded_image)
    response = get_list(api_client)
    assert_image_fields_exist(response.data["data"][0])


@pytest.mark.django_db
def test_image_id_is_audit_logged_on_get_detail(user_api_client, image):
    response = get_detail(user_api_client, image.pk)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [image.pk]


@pytest.mark.django_db
def test_image_id_is_audit_logged_on_get_list(user_api_client, image, image2):
    response = get_list(user_api_client)
    assert response.status_code == status.HTTP_200_OK

    audit_log_entry = AuditLogEntry.objects.first()
    assert Counter(
        audit_log_entry.message["audit_event"]["target"]["object_ids"]
    ) == Counter([image.pk, image2.pk])


@pytest.mark.django_db
def test_get_image_list_check_fields_exist_for_url(api_client):
    Image.objects.create(
        url="https://commons.wikimedia.org/wiki/File:Common_Squirrel.jpg"
    )
    response = get_list(api_client)
    assert_image_fields_exist(response.data["data"][0])


@pytest.mark.django_db
def test_get_image_list_verify_text_filter(api_client, image, image2, image3):
    response = api_client.get(reverse("image-list"), data={"text": "kuva"})
    assert image.id in [entry["id"] for entry in response.data["data"]]
    assert image2.id not in [entry["id"] for entry in response.data["data"]]
    assert image3.id not in [entry["id"] for entry in response.data["data"]]


@pytest.mark.django_db
def test_get_detail_check_fields_exist(api_client):
    uploaded_image = create_uploaded_image()
    existing_image = Image.objects.create(image=uploaded_image)
    response = get_detail(api_client, existing_image.pk)
    assert_image_fields_exist(response.data)


@pytest.mark.django_db
def test_get_detail_check_fields_exist_for_url(api_client):
    existing_image = Image.objects.create(
        url="https://commons.wikimedia.org/wiki/File:Common_Squirrel.jpg"
    )
    response = get_detail(api_client, existing_image.pk)
    assert_image_fields_exist(response.data)


@pytest.mark.django_db
def test_get_detail_check_image_url(api_client):
    uploaded_image = create_uploaded_image()
    existing_image = Image.objects.create(image=uploaded_image)
    response = get_detail(api_client, existing_image.pk)
    assert "images/existing_test_image" in response.data["url"]
    assert response.data["url"].endswith(".png")


@pytest.mark.django_db
def test_unauthenticated_user_cannot_upload_an_image(api_client, list_url, image_data):
    response = api_client.post(list_url, image_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_unauthenticated_user_cannot_upload_a_url(api_client, list_url, image_url):
    response = api_client.post(list_url, image_url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_upload_an_image(api_client, list_url, image_data, user, organization):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)

    response = api_client.post(list_url, image_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert Image.objects.all().count() == 1

    image = Image.objects.get(pk=response.data["id"])
    assert image.created_by == user
    assert image.last_modified_by == user
    assert image.publisher == organization

    # image url should contain the image file's path relative to MEDIA_ROOT.
    assert image.image.url.startswith("/images/test_image")
    assert image.image.url.endswith(".png")

    # check the actual image file
    image = PILImage.open(image.image.path)
    assert image.size == (512, 256)
    assert image.format == "PNG"


@pytest.mark.django_db
def test_upload_an_image_with_api_key(
    api_client, list_url, image_data, data_source, organization
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = api_client.post(list_url, image_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert Image.objects.all().count() == 1
    assert ApiKeyUser.objects.all().count() == 1

    image = Image.objects.get(pk=response.data["id"])
    assert image.publisher == organization

    # image url should contain the image file's path relative to MEDIA_ROOT.
    assert image.image.url.startswith("/images/test_image")
    assert image.image.url.endswith(".png")

    # check the actual image file
    image = PILImage.open(image.image.path)
    assert image.size == (512, 256)
    assert image.format == "PNG"


@pytest.mark.django_db
def test_image_edit_as_superuser(
    api_client, list_url, image_data, user, organization, organization2, user2
):
    expected_name = "this is needed"
    organization.admin_users.add(user)
    organization2.admin_users.add(user2)
    user2.is_superuser = True
    api_client.force_authenticate(user)

    response = api_client.post(list_url, image_data)

    api_client.force_authenticate(user2)
    detail_url = reverse("image-detail", kwargs={"pk": response.data["id"]})

    response2 = api_client.put(detail_url, {"name": expected_name})

    assert response2.status_code == status.HTTP_200_OK
    image = Image.objects.get(pk=response.data["id"])
    assert image.name == expected_name


@pytest.mark.django_db
def test_image_upload_as_external(api_client, external_user, list_url, image_data):
    api_client.force_authenticate(external_user)

    response = api_client.post(list_url, image_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert Image.objects.all().count() == 1

    image = Image.objects.get(pk=response.data["id"])
    assert image.created_by == external_user
    assert image.last_modified_by == external_user


@pytest.mark.django_db
def test_image_edit_as_external(api_client, external_user):
    expected_name = "this is needed"
    uploaded_image = create_uploaded_image()
    image = Image.objects.create(image=uploaded_image, created_by=external_user)
    api_client.force_authenticate(external_user)
    detail_url = reverse("image-detail", kwargs={"pk": image.id})

    response = api_client.put(detail_url, {"name": expected_name})

    assert response.status_code == status.HTTP_200_OK
    image.refresh_from_db()
    assert image.name == expected_name


@pytest.mark.django_db
def test_image_upload_and_edit_as_admin(
    api_client, list_url, image_data, user, organization, user2
):
    expected_name = "this is needed"
    organization.admin_users.add(user)
    organization.admin_users.add(user2)
    api_client.force_authenticate(user)

    response = api_client.post(list_url, image_data)

    api_client.force_authenticate(user2)

    image = Image.objects.get(pk=response.data["id"])
    assert user2.is_admin_of(image.publisher) is True

    detail_url = reverse("image-detail", kwargs={"pk": response.data["id"]})
    response2 = api_client.put(detail_url, {"name": expected_name})
    assert response2.status_code == status.HTTP_200_OK
    image.refresh_from_db()
    assert image.name == expected_name


@pytest.mark.django_db
def test_image_upload_and_edit_as_regular_user(
    api_client, list_url, image_data, user, organization, user2
):
    organization.regular_users.add(user)
    api_client.force_authenticate(user)

    response = api_client.post(list_url, image_data)

    organization.regular_users.add(user2)
    api_client.force_authenticate(user2)

    image = Image.objects.get(pk=response.data["id"])
    assert user2.is_regular_user_of(image.publisher) is True

    detail_url = reverse("image-detail", kwargs={"pk": response.data["id"]})
    response2 = api_client.put(detail_url, {"name": "this is needed"})
    assert response2.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_image_cannot_be_edited_outside_organization(
    api_client, list_url, image_data, user, organization, organization2, user2
):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)

    response = api_client.post(list_url, image_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert Image.objects.all().count() == 1

    image = Image.objects.get(pk=response.data["id"])
    assert image.created_by == user
    assert image.last_modified_by == user
    assert image.publisher == organization

    # other users cannot edit the image
    organization2.admin_users.add(user2)
    api_client.force_authenticate(user2)
    detail_url = reverse("image-detail", kwargs={"pk": response.data["id"]})
    response2 = api_client.put(detail_url, {"name": "this is needed"})
    assert response2.status_code == 403


@pytest.mark.django_db
def test_image_from_another_data_source_can_be_edited_by_admin(
    api_client, list_url, image_data, data_source, user, organization, other_data_source
):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)

    response = api_client.post(list_url, image_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert Image.objects.all().count() == 1

    image = Image.objects.get(pk=response.data["id"])
    assert image.created_by == user
    assert image.last_modified_by == user
    assert image.publisher == organization
    assert image.data_source == data_source
    image.data_source = other_data_source
    image.save()
    other_data_source.user_editable_resources = True
    other_data_source.owner = organization
    other_data_source.save()
    assert image.data_source == other_data_source
    assert other_data_source in organization.owned_systems.all()

    # user can still edit the image
    detail_url = reverse("image-detail", kwargs={"pk": response.data["id"]})
    response2 = api_client.put(
        detail_url, {"id": response.data["id"], "name": "this is needed"}
    )
    assert response2.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_image_cannot_be_edited_outside_organization_with_apikey(
    api_client,
    list_url,
    image_data,
    user,
    organization,
    organization2,
    other_data_source,
):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)

    response = api_client.post(list_url, image_data)
    assert response.status_code == status.HTTP_201_CREATED
    assert Image.objects.all().count() == 1

    image = Image.objects.get(pk=response.data["id"])
    assert image.created_by == user
    assert image.last_modified_by == user
    assert image.publisher == organization

    # api key user cannot edit the image
    other_data_source.owner = organization2
    other_data_source.save()
    api_client.force_authenticate(user=None)
    api_client.credentials(apikey=other_data_source.api_key)

    detail_url = reverse("image-detail", kwargs={"pk": response.data["id"]})
    response2 = api_client.put(detail_url, {"name": "this is needed"})
    assert response2.status_code == 403


@pytest.mark.django_db
def test_create_an_event_with_uploaded_image(
    api_client, list_url, minimal_event_dict, image_data, user
):
    api_client.force_authenticate(user)

    image_response = api_client.post(list_url, image_data)
    assert image_response.status_code == status.HTTP_201_CREATED
    assert Image.objects.all().count() == 1

    image = Image.objects.get(pk=image_response.data["id"])
    assert image.created_by == user
    assert image.last_modified_by == user

    minimal_event_dict.update({"images": [{"@id": str(image_response.data["@id"])}]})
    response = create_with_post(api_client, minimal_event_dict)

    # the event data should contain the expanded image data
    minimal_event_dict["images"][0].update(image_response.data)
    # the image field url changes between endpoints
    # also, admin only fields are not displayed in inlined resources
    minimal_event_dict["images"][0].pop("url")
    minimal_event_dict["images"][0].pop("created_by")
    minimal_event_dict["images"][0].pop("last_modified_by")
    assert_event_data_is_equal(minimal_event_dict, response.data)


@pytest.mark.django_db
def test_update_an_event_with_uploaded_image(
    api_client, list_url, minimal_event_dict, image_data, user
):
    api_client.force_authenticate(user)
    response = create_with_post(api_client, minimal_event_dict)

    image_response = api_client.post(list_url, image_data)
    assert image_response.status_code == status.HTTP_201_CREATED
    assert Image.objects.all().count() == 1

    image = Image.objects.get(pk=image_response.data["id"])
    assert image.created_by == user
    assert image.last_modified_by == user

    minimal_event_dict.update({"images": [{"@id": str(image_response.data["@id"])}]})
    response2 = update_with_put(api_client, response.data["@id"], minimal_event_dict)

    # the event data should contain the expanded image data
    minimal_event_dict["images"][0].update(image_response.data)
    # the image field url changes between endpoints
    # also, admin only fields are not displayed in inlined resources
    minimal_event_dict["images"][0].pop("url")
    minimal_event_dict["images"][0].pop("created_by")
    minimal_event_dict["images"][0].pop("last_modified_by")
    assert_event_data_is_equal(minimal_event_dict, response2.data)


@pytest.mark.django_db
def test_upload_a_url(api_client, list_url, image_url, user, organization):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)

    response = api_client.post(list_url, image_url)
    assert response.status_code == status.HTTP_201_CREATED
    assert Image.objects.all().count() == 1

    image = Image.objects.get(pk=response.data["id"])
    assert image.created_by == user
    assert image.last_modified_by == user

    # image url should stay the same as when input
    assert image.url == "https://commons.wikimedia.org/wiki/File:Common_Squirrel.jpg"


@pytest.mark.django_db
def test_upload_a_url_with_alt_text(
    api_client, list_url, image_url, user, organization
):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)

    image_url = image_url.copy()
    image_url["alt_text"] = "Lorem"

    response = api_client.post(list_url, image_url)
    assert response.status_code == status.HTTP_201_CREATED
    assert Image.objects.all().count() == 1

    image = Image.objects.get(pk=response.data["id"])
    assert image.created_by == user
    assert image.last_modified_by == user
    assert image.alt_text == "Lorem"


@pytest.mark.django_db
def test_upload_a_url_with_api_key(
    api_client, list_url, image_url, data_source, organization
):
    data_source.owner = organization
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    response = api_client.post(list_url, image_url)
    assert response.status_code == status.HTTP_201_CREATED
    assert Image.objects.all().count() == 1
    assert ApiKeyUser.objects.all().count() == 1

    image = Image.objects.get(pk=response.data["id"])
    assert image.publisher == organization

    # image url should stay the same as when input
    assert image.url == "https://commons.wikimedia.org/wiki/File:Common_Squirrel.jpg"


@pytest.mark.django_db
def test_upload_an_image_and_url(
    api_client, list_url, image_data, image_url, user, organization
):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)

    image_data_and_url = image_data.copy()
    image_data_and_url.update(image_url)
    response = api_client.post(list_url, image_data_and_url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    for line in response.data:
        assert "You can only provide image or url, not both" in line


@pytest.mark.django_db
def test_upload_a_non_valid_image(api_client, list_url, user, organization):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)

    non_image_file = BytesIO(bytes(random.getrandbits(8) for _ in range(100)))

    response = api_client.post(list_url, {"image": non_image_file})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "image" in response.data


@pytest.mark.django_db
def test_upload_an_invalid_dict(api_client, list_url, user, organization):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)
    response = api_client.post(list_url, {"name": "right", "key": "wrong"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    for line in response.data:
        assert "You must provide either image or url" in line


@pytest.mark.django_db
def test_image_upload_cannot_set_arbitrary_publisher(
    api_client, external_user, list_url, image_data, organization
):
    image_data["name"] = "image name"
    image_data["publisher"] = organization.id
    api_client.force_authenticate(external_user)

    response = api_client.post(list_url, image_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "publisher" in response.data


@pytest.mark.django_db
def test_set_image_license(
    api_client, list_url, image_data, image_url, user, organization
):
    organization.admin_users.add(user)
    api_client.force_authenticate(user)

    # an image is posted without a license, expect cc_by
    response = api_client.post(list_url, image_url)
    assert response.status_code == status.HTTP_201_CREATED
    new_image = Image.objects.last()
    assert new_image.license_id == "cc_by"

    # an image is posted with event_only license, expect change
    image_data["license"] = "event_only"
    response = api_client.post(list_url, image_data)
    assert response.status_code == status.HTTP_201_CREATED
    new_image = Image.objects.last()
    assert new_image.license_id == "event_only"

    # the same image is put without a license, expect event_only license not changed
    response = api_client.put(
        "%s%s/" % (list_url, new_image.id), {"name": "this is needed"}
    )
    assert response.status_code == status.HTTP_200_OK
    new_image.refresh_from_db()
    assert new_image.license_id == "event_only"

    # the same image is put with cc_by license, expect change
    response = api_client.put(
        "%s%s/" % (list_url, new_image.id),
        {"name": "this is needed", "license": "cc_by"},
    )
    assert response.status_code == status.HTTP_200_OK
    new_image.refresh_from_db()
    assert new_image.license_id == "cc_by"
