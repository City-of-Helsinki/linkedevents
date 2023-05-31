import pytest
from rest_framework import status

from ..models import PublicationStatus
from .factories import (
    DataSourceFactory,
    DefaultOrganizationEventFactory,
    EventFactory,
    OrganizationFactory,
)
from .utils import assert_event_data_is_equal
from .utils import versioned_reverse as reverse


@pytest.fixture(autouse=True)
def setup(settings):
    settings.EXTERNAL_USER_PUBLISHER_ID = "others"
    settings.ENABLE_EXTERNAL_USER_EVENTS = True


@pytest.fixture
def make_event_data(make_minimal_event_dict, location_id):
    def _make_minimal_event_dict(event, **kwargs):
        kwargs.setdefault("publication_status", "draft")
        d = make_minimal_event_dict(event.data_source, event.publisher, location_id)
        d["publisher"] = None
        # Required fields for external user
        d["user_email"] = "email@example.com"
        d["user_name"] = "User name"
        d["maximum_attendee_capacity"] = 5
        d["user_consent"] = True
        d.update(kwargs)
        return d

    return _make_minimal_event_dict


@pytest.fixture
def minimal_event(minimal_event_dict):
    minimal_event_dict["publisher"] = None
    minimal_event_dict["publication_status"] = "draft"
    # Required fields for external user
    minimal_event_dict["user_email"] = "email@example.com"
    minimal_event_dict["user_name"] = "User name"
    minimal_event_dict["maximum_attendee_capacity"] = 5
    minimal_event_dict["user_consent"] = True

    return minimal_event_dict


@pytest.fixture
def authed_api_client(api_client, external_user):
    api_client.force_authenticate(user=external_user)
    return api_client


def create(api_client, event_data):
    create_url = reverse("event-list")
    return api_client.post(create_url, event_data, format="json")


def bulk_create(api_client, event_data):
    create_url = reverse("event-list")
    return api_client.post(create_url, event_data, format="json")


def update(api_client, event_id, event_data):
    url = reverse("event-detail", kwargs={"pk": event_id})
    return api_client.put(url, event_data, format="json")


def bulk_update(api_client, event_data):
    url = reverse("event-list")
    return api_client.put(url, event_data, format="json")


def delete(api_client, event_id):
    url = reverse("event-detail", kwargs={"pk": event_id})
    return api_client.delete(url)


class TestEventCreate:
    @pytest.mark.django_db
    def test_should_be_able_to_create_event_draft(
        self, authed_api_client, minimal_event, external_user
    ):
        response = create(authed_api_client, minimal_event)

        minimal_event["publisher"] = "others"
        assert_event_data_is_equal(minimal_event, response.data)

    @pytest.mark.django_db
    def test_should_not_be_able_to_create_and_publish_event(
        self,
        authed_api_client,
        minimal_event,
        external_user,
    ):
        minimal_event["publication_status"] = "public"

        response = create(authed_api_client, minimal_event)
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_should_not_be_able_to_create_event_draft_if_external_user_events_are_disabled(
        self, authed_api_client, minimal_event, external_user, settings
    ):
        settings.ENABLE_EXTERNAL_USER_EVENTS = False
        response = create(authed_api_client, minimal_event)

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data


class TestEventBulkCreate:
    @pytest.mark.django_db
    def test_should_be_able_to_bulk_create_draft_events(
        self, authed_api_client, minimal_event, external_user
    ):
        response = bulk_create(authed_api_client, [minimal_event, minimal_event])

        minimal_event["publisher"] = "others"
        assert_event_data_is_equal(minimal_event, response.data[0])
        assert_event_data_is_equal(minimal_event, response.data[1])


class TestEventUpdate:
    @pytest.mark.django_db
    def test_should_be_able_to_edit_own_event_draft(
        self, authed_api_client, make_event_data, external_user
    ):
        event = DefaultOrganizationEventFactory(
            created_by=external_user, publication_status=PublicationStatus.DRAFT
        )

        response = update(authed_api_client, event.id, make_event_data(event))

        assert response.status_code == status.HTTP_200_OK, response.data

    @pytest.mark.django_db
    def test_should_not_be_able_to_edit_own_event_published(
        self, authed_api_client, make_event_data, external_user
    ):
        event = DefaultOrganizationEventFactory(created_by=external_user)

        response = update(
            authed_api_client,
            event.id,
            make_event_data(event, publication_status="public"),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    @pytest.mark.django_db
    def test_should_not_be_able_to_edit_others_event_draft(
        self, authed_api_client, external_user, external_user_2, make_event_data
    ):
        event = DefaultOrganizationEventFactory(
            created_by=external_user_2, publication_status=PublicationStatus.DRAFT
        )

        response = update(authed_api_client, event.id, make_event_data(event))

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    @pytest.mark.django_db
    def test_should_not_be_able_to_edit_own_draft_in_non_default_organization(
        self, authed_api_client, external_user, make_event_data
    ):
        data_source = DataSourceFactory(user_editable_resources=True)
        organization = OrganizationFactory(id="acme", data_source=data_source)
        event = EventFactory(
            created_by=external_user,
            data_source=data_source,
            publication_status=PublicationStatus.DRAFT,
            publisher=organization,
        )

        response = update(authed_api_client, event.id, make_event_data(event))

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    @pytest.mark.django_db
    def test_should_not_be_able_to_edit_own_event_draft_if_external_user_events_are_disabled(
        self, authed_api_client, make_event_data, external_user, settings
    ):
        settings.ENABLE_EXTERNAL_USER_EVENTS = False
        event = DefaultOrganizationEventFactory(
            created_by=external_user, publication_status=PublicationStatus.DRAFT
        )

        response = update(authed_api_client, event.id, make_event_data(event))

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data


class TestEventBulkUpdate:
    @pytest.mark.django_db
    def test_should_be_able_to_edit_own_events_draft(
        self, authed_api_client, make_event_data, external_user
    ):
        event1 = DefaultOrganizationEventFactory(
            created_by=external_user, publication_status=PublicationStatus.DRAFT
        )
        event2 = DefaultOrganizationEventFactory(
            created_by=external_user, publication_status=PublicationStatus.DRAFT
        )
        event_data1 = make_event_data(event1)
        event_data2 = make_event_data(event2)
        event_data1["id"] = event1.id
        event_data2["id"] = event2.id
        event_data = [event_data1, event_data2]

        response = bulk_update(authed_api_client, event_data)

        assert response.status_code == status.HTTP_200_OK, response.data

    @pytest.mark.django_db
    def test_should_not_be_able_to_edit_own_events_published(
        self, authed_api_client, make_event_data, external_user
    ):
        event1 = DefaultOrganizationEventFactory(
            created_by=external_user, publication_status=PublicationStatus.PUBLIC
        )
        event2 = DefaultOrganizationEventFactory(
            created_by=external_user, publication_status=PublicationStatus.DRAFT
        )
        event_data1 = make_event_data(event1)
        event_data2 = make_event_data(event2)
        event_data1["id"] = event1.id
        event_data2["id"] = event2.id
        event_data = [event_data1, event_data2]

        response = bulk_update(authed_api_client, event_data)

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    @pytest.mark.django_db
    def test_should_not_be_able_to_edit_others_event_draft(
        self, authed_api_client, external_user, external_user_2, make_event_data
    ):
        event = DefaultOrganizationEventFactory(
            created_by=external_user_2, publication_status=PublicationStatus.DRAFT
        )

        response = update(authed_api_client, event.id, make_event_data(event))

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data


class TestEventDelete:
    @pytest.mark.django_db
    def test_should_be_able_to_delete_own_event_draft(
        self, authed_api_client, external_user
    ):
        event = DefaultOrganizationEventFactory(
            created_by=external_user, publication_status=PublicationStatus.DRAFT
        )

        response = delete(authed_api_client, event.id)

        assert response.status_code == status.HTTP_204_NO_CONTENT, response.data

    @pytest.mark.django_db
    def test_should_not_be_able_to_delete_own_event_published(
        self, authed_api_client, external_user
    ):
        event = DefaultOrganizationEventFactory(created_by=external_user)

        response = delete(authed_api_client, event.id)

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data

    @pytest.mark.django_db
    def test_should_not_be_able_to_delete_others_event_draft(
        self, authed_api_client, external_user, external_user_2
    ):
        event = DefaultOrganizationEventFactory(
            created_by=external_user_2, publication_status=PublicationStatus.DRAFT
        )

        response = delete(authed_api_client, event.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data

    @pytest.mark.django_db
    def test_should_not_be_able_to_delete_own_event_draft_if_external_user_events_are_disabled(
        self, authed_api_client, external_user, settings
    ):
        settings.ENABLE_EXTERNAL_USER_EVENTS = False
        event = DefaultOrganizationEventFactory(
            created_by=external_user, publication_status=PublicationStatus.DRAFT
        )

        response = delete(authed_api_client, event.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.data
