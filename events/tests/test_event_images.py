# -*- coding: utf-8 -*-
import os
import tempfile
import shutil
from io import BytesIO
import random
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from PIL import Image

from .utils import get, assert_fields_exist
from events.models import EventImage


temp_dir = tempfile.mkdtemp()


@pytest.yield_fixture(autouse=True)
def tear_down():
    yield
    shutil.rmtree(temp_dir, ignore_errors=True)


# === util methods ===


def create_in_memory_image_file(name='test_image', image_format='png', size=(512, 256), color=(128, 128, 128)):
    image = Image.new('RGBA', size=size, color=color)
    file = BytesIO()
    file.name = '{}.{}'.format(name, image_format)
    image.save(file, format=image_format)
    file.seek(0)
    return file


def get_list(api_client):
    list_url = reverse('eventimage-list')
    return get(api_client, list_url)


def get_detail(api_client, detail_pk):
    detail_url = reverse('eventimage-detail', kwargs={'pk': detail_pk})
    return get(api_client, detail_url)


def assert_event_image_fields_exist(data):
    fields = (
        '@context',
        '@id',
        '@type',
        'created_time',
        'cropping',
        'id',
        'image',
        'last_modified_by',
        'last_modified_time',
    )
    assert_fields_exist(data, fields)


# === fixtures ===


@pytest.fixture
def list_url():
    return reverse('eventimage-list')


@pytest.fixture
def event_image_data():
    image_file = create_in_memory_image_file()
    return {
        'image': image_file,
    }


# === tests ===


@pytest.mark.django_db
def test__get_event_image_list_check_fields_exist(api_client):
    image_file = create_in_memory_image_file(name='existing_test_image')
    uploaded_image = SimpleUploadedFile(
        'existing_test_image.png',
        image_file.read(),
        'image/png',
    )
    EventImage.objects.create(image=uploaded_image)
    response = get_list(api_client)
    assert_event_image_fields_exist(response.data['data'][0])


@pytest.mark.django_db
def test__get_event_detail_check_fields_exist(api_client):
    image_file = create_in_memory_image_file(name='existing_test_image')
    uploaded_image = SimpleUploadedFile(
        'existing_test_image.png',
        image_file.read(),
        'image/png',
    )
    existing_event_image = EventImage.objects.create(image=uploaded_image)
    response = get_detail(api_client, existing_event_image.pk)
    assert_event_image_fields_exist(response.data)


@pytest.mark.django_db
def test__unauthenticated_user_cannot_upload_an_event_image(api_client, list_url, event_image_data, user):
    response = api_client.post(list_url, event_image_data)
    assert response.status_code == 401


@override_settings(MEDIA_ROOT=temp_dir, MEDIA_URL='')
@pytest.mark.django_db
def test__upload_an_event_image(api_client, settings, list_url, event_image_data, user):
    api_client.force_authenticate(user)

    response = api_client.post(list_url, event_image_data)
    assert response.status_code == 201
    assert EventImage.objects.all().count() == 1

    event_image = EventImage.objects.get(pk=response.data['id'])
    assert event_image.created_by == user
    assert event_image.last_modified_by == user

    # image url should contain the image file's path relative to MEDIA_ROOT.
    image_url = event_image.image.url
    assert image_url.startswith('event_images/test_image')
    assert image_url.endswith('.png')

    # check the actual image file
    image_path = os.path.join(settings.MEDIA_ROOT, event_image.image.url)
    image = Image.open(image_path)
    assert image.size == (512, 256)
    assert image.format == 'PNG'


@override_settings(MEDIA_ROOT=temp_dir, MEDIA_URL='')
@pytest.mark.django_db(transaction=True)  # transaction is needed for django-cleanup
def test__delete_an_event_image(api_client, settings, user):
    api_client.force_authenticate(user)

    image_file = create_in_memory_image_file(name='existing_test_image')
    uploaded_image = SimpleUploadedFile(
        'existing_test_image.png',
        image_file.read(),
        'image/png',
    )
    existing_event_image = EventImage.objects.create(image=uploaded_image)
    assert EventImage.objects.all().count() == 1

    # verify that the image file exists at first just in case
    image_path = os.path.join(settings.MEDIA_ROOT, existing_event_image.image.url)
    assert os.path.isfile(image_path)

    detail_url = reverse('eventimage-detail', kwargs={'pk': existing_event_image.pk})
    response = api_client.delete(detail_url)
    assert response.status_code == 204
    assert EventImage.objects.all().count() == 0

    # check that the image file is deleted
    assert not os.path.isfile(image_path)


@override_settings(MEDIA_ROOT=temp_dir, MEDIA_URL='')
@pytest.mark.django_db
def test__upload_a_non_valid_image(api_client, list_url, user):
    api_client.force_authenticate(user)

    non_image_file = BytesIO(bytes(random.getrandbits(8) for _ in range(100)))

    response = api_client.post(list_url, {'image': non_image_file})
    assert response.status_code == 400
    assert 'image' in response.data
