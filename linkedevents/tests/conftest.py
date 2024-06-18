import shutil

import pytest
import sentry_sdk
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django_orghierarchy.models import Organization, OrganizationClass
from rest_framework.test import APIClient
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from events.models import DataSource

OTHER_DATA_SOURCE_ID = "testotherdatasourceid"

# Django test harness tries to serialize DB in order to support transactions
# within tests. (It restores the snapshot after such tests).
# This fails with modeltranslate, as the serialization is done before
# sync_translation_fields has a chance to run. Thus the fields are missing
# and serialization fails horribly.


@pytest.fixture(scope="session")
def django_db_modify_db_settings(django_db_modify_db_settings_xdist_suffix):
    settings.DATABASES["default"]["TEST"]["SERIALIZE"] = False


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("sync_translation_fields", "--noinput")


@pytest.fixture(autouse=True)
def setup_test_media(settings):
    """Create folder for test media/file uploads."""
    settings.MEDIA_ROOT = "test_media"
    settings.MEDIA_URL = ""
    yield
    shutil.rmtree("test_media", ignore_errors=True)


@pytest.fixture
def user():
    return get_user_model().objects.create(
        username="test_user", first_name="Cem", last_name="Kaner", email="cem@kaner.com"
    )


@pytest.fixture
def user2():
    return get_user_model().objects.create(
        username="test_user2",
        first_name="Brendan",
        last_name="Neutra",
        email="brendan@neutra.com",
    )


@pytest.fixture
def external_user():
    """A user that doesn't belong to any organization."""
    return get_user_model().objects.create(
        username="external_user",
        first_name="External",
        last_name="User",
        email="external@user.test",
    )


@pytest.fixture
def external_user_2():
    """Another user that doesn't belong to any organization."""
    return get_user_model().objects.create(
        username="external_user_2",
        first_name="External2",
        last_name="User",
        email="external2@user.test",
    )


@pytest.fixture
def super_user():
    return get_user_model().objects.create(
        username="super_user",
        first_name="Super",
        last_name="Man",
        email="super@user.com",
        is_superuser=True,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture()
def user_api_client(user):
    api_client = APIClient()
    api_client.force_authenticate(user)
    return api_client


@pytest.fixture
def data_source(settings):
    return DataSource.objects.create(
        id=settings.SYSTEM_DATA_SOURCE_ID,
        api_key="test_api_key",
        user_editable_resources=True,
        user_editable_organizations=True,
    )


@pytest.fixture
def other_data_source():
    return DataSource.objects.create(id=OTHER_DATA_SOURCE_ID, api_key="test_api_key2")


@pytest.mark.django_db
@pytest.fixture
def organization_class():
    return OrganizationClass.objects.create(
        name="test_organization_class",
    )


@pytest.mark.django_db
@pytest.fixture
def organization(data_source, user):
    """Organization with a single admin user (user)."""
    org, created = Organization.objects.get_or_create(
        id=data_source.id + ":test_organization",
        origin_id="test_organization",
        name="test_organization",
        data_source=data_source,
    )
    org.admin_users.add(user)
    org.save()
    return org


@pytest.mark.django_db
@pytest.fixture
def organization2(other_data_source, user2):
    """Organization with a single admin user (user2)."""
    org, created = Organization.objects.get_or_create(
        id=other_data_source.id + ":test_organization2",
        origin_id="test_organization2",
        name="test_organization2",
        data_source=other_data_source,
    )
    org.admin_users.add(user2)
    org.save()
    return org


@pytest.mark.django_db
@pytest.fixture
def organization3(other_data_source, user2):
    """Organization with a single admin user (user2)."""
    org, created = Organization.objects.get_or_create(
        id=other_data_source.id + ":test_organization3",
        origin_id="test_organization3",
        name="test_organization3",
        data_source=other_data_source,
    )
    org.admin_users.add(user2)
    org.save()
    return org


@pytest.fixture
def django_cache():
    yield cache
    cache.clear()


class TestTransport(Transport):
    """Copied from https://github.com/getsentry/sentry-python/blob/master/tests/conftest.py."""

    def __init__(self):
        Transport.__init__(self)

    def capture_envelope(self, _: Envelope) -> None:
        """No-op capture_envelope for tests"""
        pass


@pytest.fixture
def sentry_init(request):
    """Copied from https://github.com/getsentry/sentry-python/blob/master/tests/conftest.py."""

    def inner(*a, **kw):
        hub = sentry_sdk.Hub.current
        kw.setdefault("transport", TestTransport())
        client = sentry_sdk.Client(*a, **kw)
        hub.bind_client(client)

    if request.node.get_closest_marker("forked"):
        # Do not run isolation if the test is already running in
        # ultimate isolation (seems to be required for celery tests that
        # fork)
        yield inner
    else:
        with sentry_sdk.Hub(None):
            yield inner


@pytest.fixture
def sentry_capture_events(monkeypatch):
    """Copied from https://github.com/getsentry/sentry-python/blob/master/tests/conftest.py."""

    def inner():
        events = []
        test_client = sentry_sdk.Hub.current.client
        old_capture_envelope = test_client.transport.capture_envelope

        def append_event(envelope):
            for item in envelope:
                if item.headers.get("type") in ("event", "transaction"):
                    events.append(item.payload.json)
            return old_capture_envelope(envelope)

        monkeypatch.setattr(test_client.transport, "capture_envelope", append_event)

        return events

    return inner
