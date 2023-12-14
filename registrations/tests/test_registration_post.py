import pytest
from django.utils import translation
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.tests.utils import assert_invitation_email_is_sent

email = "user@email.com"
event_name = "Foo"

# === util methods ===


def create_registration(api_client, registration_data, data_source=None):
    if data_source:
        api_client.credentials(apikey=data_source.api_key)

    create_url = reverse("registration-list")
    response = api_client.post(create_url, registration_data, format="json")
    return response


def assert_create_registration(api_client, registration_data, data_source=None):
    response = create_registration(api_client, registration_data, data_source)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["event"] == registration_data["event"]

    return response


def get_event_url(detail_pk):
    return reverse("event-detail", kwargs={"pk": detail_pk})


# === tests ===


@pytest.mark.django_db
def test_create_registration(user, api_client, event):
    api_client.force_authenticate(user)
    registration_data = {"event": {"@id": get_event_url(event.id)}}

    assert_create_registration(api_client, registration_data)


@pytest.mark.django_db
def test_superuser_can_create_registration(api_client, event):
    user = UserFactory(is_superuser=True)
    api_client.force_authenticate(user)

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    assert_create_registration(api_client, registration_data)


@pytest.mark.django_db
def test_only_one_registration_per_event_is_allowed(
    user, api_client, event, registration
):
    api_client.force_authenticate(user)
    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_cannot_create_registration_with_event_in_invalid_format(
    api_client, organization, user
):
    api_client.force_authenticate(user)
    registration_data = {"event": "invalid-format"}

    response = create_registration(api_client, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["event"][0] == "Incorrect JSON. Expected JSON, received str."


@pytest.mark.django_db
def test_cannot_create_registration_with_nonexistent_event(
    api_client, organization, user
):
    api_client.force_authenticate(user)
    registration_data = {"event": {"@id": "nonexistent-id"}}

    response = create_registration(api_client, registration_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_maximum_group_size_cannot_be_less_than_one(user, api_client, event):
    api_client.force_authenticate(user)
    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "maximum_group_size": 0,
    }

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["maximum_group_size"][0].code == "min_value"


@pytest.mark.django_db
def test__unauthenticated_user_cannot_create_registration(api_client, event):
    api_client.force_authenticate(None)
    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__non_admin_cannot_create_registration(api_client, event, user):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)
    api_client.force_authenticate(user)

    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_financial_admin_cannot_create_registration(api_client, event):
    user = UserFactory()
    user.financial_admin_organizations.add(event.publisher)
    api_client.force_authenticate(user)

    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__user_from_other_organization_cannot_create_registration(
    api_client, event, user2
):
    api_client.force_authenticate(user2)

    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_can_create_registration_with_datasource_permission_missing(
    api_client, event, other_data_source, user
):
    event.data_source = other_data_source
    event.save()
    api_client.force_authenticate(user)

    registration_data = {"event": {"@id": get_event_url(event.id)}}

    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test__api_key_with_organization_can_create_registration(
    api_client, data_source, event, organization
):
    data_source.owner = organization
    data_source.save()

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    assert_create_registration(api_client, registration_data, data_source)


@pytest.mark.django_db
def test__api_key_with_wrong_data_source_cannot_create_registration(
    api_client, data_source, event, organization, other_data_source
):
    other_data_source.owner = organization
    other_data_source.save()

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    response = create_registration(api_client, registration_data, other_data_source)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test__unknown_api_key_cannot_create_registration(api_client, event):
    api_client.credentials(apikey="unknown")

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test__empty_api_key_cannot_create_registration(api_client, event):
    api_client.credentials(apikey="")

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    response = create_registration(api_client, registration_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.django_db
def test_admin_can_create_registration_regardless_of_non_user_editable_resources(
    user_api_client, data_source, event, organization, user_editable_resources
):
    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    assert_create_registration(user_api_client, registration_data)


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.django_db
def test_registration_admin_can_create_registration_regardless_of_non_user_editable_resources(
    user_api_client, data_source, event, organization, user, user_editable_resources
):
    user.get_default_organization().registration_admin_users.add(user)

    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    assert_create_registration(user_api_client, registration_data)


@pytest.mark.django_db
def test__user_editable_resources_can_create_registration(
    api_client, data_source, event, organization, user
):
    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save()
    api_client.force_authenticate(user=user)

    registration_data = {"event": {"@id": get_event_url(event.id)}}
    assert_create_registration(api_client, registration_data, data_source)


@pytest.mark.django_db
def test__send_email_to_registration_user_access(event, user_api_client):
    with translation.override("fi"):
        event.type_id = Event.TypeId.GENERAL
        event.name = event_name
        event.save()

        registration_data = {
            "event": {"@id": get_event_url(event.id)},
            "registration_user_accesses": [{"email": email}],
        }
        assert_create_registration(user_api_client, registration_data)
        #  assert that the email was sent
        assert_invitation_email_is_sent(email, event_name)


@pytest.mark.django_db
def test__cannot_create_registration_user_accesses_with_duplicate_emails(
    event, user_api_client
):
    with translation.override("fi"):
        event.type_id = Event.TypeId.GENERAL
        event.name = event_name
        event.save()

        registration_data = {
            "event": {"@id": get_event_url(event.id)},
            "registration_user_accesses": [{"email": email}, {"email": email}],
        }
        response = create_registration(user_api_client, registration_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["registration_user_accesses"][1]["email"][0].code == "unique"
        )


@pytest.mark.django_db
def test_registration_text_fields_are_sanitized(event, user_api_client):
    allowed_confirmation_message = "Confirmation message: <p>Allowed tag</p>"
    cleaned_confirmation_message = "Confirmation message: Not allowed tag"
    allowed_instructions = "Instructions: <p>Allowed tag</p>"
    cleaned_instructions = "Instructions: Not allowed tag"

    registration_data = {
        "event": {"@id": get_event_url(event.id)},
        "confirmation_message": {
            "fi": allowed_confirmation_message,
            "sv": "Confirmation message: <h6>Not allowed tag</h6>",
        },
        "instructions": {
            "fi": allowed_instructions,
            "sv": "Instructions: <h6>Not allowed tag</h6>",
        },
    }

    response = assert_create_registration(user_api_client, registration_data)
    assert response.data["confirmation_message"]["fi"] == allowed_confirmation_message
    assert response.data["confirmation_message"]["sv"] == cleaned_confirmation_message
    assert response.data["instructions"]["fi"] == allowed_instructions
    assert response.data["instructions"]["sv"] == cleaned_instructions


@pytest.mark.django_db
def test_registration_id_is_audit_logged_on_post(user_api_client, event):
    registration_data = {"event": {"@id": get_event_url(event.id)}}
    response = assert_create_registration(user_api_client, registration_data)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [
        response.data["id"]
    ]
