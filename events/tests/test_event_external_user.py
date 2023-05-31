import pytest
from rest_framework import status

from events.tests.utils import get, versioned_reverse
from helevents.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def setup_event_external_user(settings):
    settings.EXTERNAL_USER_PUBLISHER_ID = "others"
    settings.ENABLE_EXTERNAL_USER_EVENTS = True


@pytest.mark.parametrize(
    "user_type,expect_fields",
    [
        ("admin", True),
        ("regular", True),
        ("other_org", False),
        ("creator", True),
        (None, False),
    ],
)
@pytest.mark.django_db
def test_get_event_personal_information_fields(
    api_client, event, organization2, user_type, expect_fields
):
    """Event creator and organization users can see content of
    personal information fields.
    """
    user = UserFactory()
    personal_info_values = {
        "user_name": "Johnny Smith",
        "user_phone_number": "+358501234567",
        "user_email": "johnny@example.com",
        "user_organization": "Example org.",
        "user_consent": True,
    }
    for key, value in personal_info_values.items():
        setattr(event, key, value)
    event.save()
    organization = event.publisher

    if user_type == "admin":
        organization.admin_users.add(user)
    elif user_type == "regular":
        organization.regular_users.add(user)
    elif user_type == "other_org":
        organization2.admin_users.add(user)
    elif user_type == "creator":
        event.created_by = user
        event.save()

    if user_type:
        api_client.force_authenticate(user=user)

    detail_url = versioned_reverse(
        "event-detail", version="v1", kwargs={"pk": event.pk}
    )
    response = get(api_client, detail_url)

    for key, value in personal_info_values.items():
        if expect_fields:
            assert response.data[key] == value
        else:
            assert key not in response.data


@pytest.mark.parametrize("external_user_field_input", [True, False])
@pytest.mark.parametrize("is_external", [True, False])
@pytest.mark.django_db
def test_external_user_create_a_minimal_event_simple_fields(
    is_external, api_client, minimal_event_dict, organization, external_user_field_input
):
    minimal_event_dict["publication_status"] = "draft"
    del minimal_event_dict["publisher"]
    minimal_event_dict["user_consent"] = True
    if is_external:
        # Unrelated personal information fields for the test
        minimal_event_dict["user_email"] = "email@example.com"
        minimal_event_dict["user_phone_number"] = "0501234567"
    if external_user_field_input:
        minimal_event_dict["user_name"] = "User name"
        minimal_event_dict["maximum_attendee_capacity"] = 5
    user = UserFactory()
    if not is_external:
        user.admin_organizations.add(organization)
    api_client.force_authenticate(user=user)

    create_url = versioned_reverse("event-list")
    response = api_client.post(create_url, minimal_event_dict, format="json")

    if is_external and external_user_field_input:
        assert response.status_code == status.HTTP_201_CREATED, str(response.content)
    elif is_external:
        assert "user_name" in response.json()
        assert "maximum_attendee_capacity" in response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST, str(
            response.content
        )
    else:
        assert response.status_code == status.HTTP_201_CREATED, str(response.content)


@pytest.mark.parametrize("has_phone", [True, False])
@pytest.mark.parametrize("has_email", [True, False])
@pytest.mark.parametrize("is_external", [True, False])
@pytest.mark.django_db
def test_external_user_create_a_minimal_event_phone_number_or_email_required(
    is_external, api_client, minimal_event_dict, organization, has_email, has_phone
):
    minimal_event_dict["publication_status"] = "draft"
    del minimal_event_dict["publisher"]
    minimal_event_dict["user_consent"] = True
    if is_external:
        # Unrelated personal information fields for the test
        minimal_event_dict["user_name"] = "User name"
        minimal_event_dict["maximum_attendee_capacity"] = 5
    if has_email:
        minimal_event_dict["user_email"] = "email@example.com"
    if has_phone:
        minimal_event_dict["user_phone_number"] = "0501234567"
    user = UserFactory()
    if not is_external:
        user.admin_organizations.add(organization)
    api_client.force_authenticate(user=user)

    create_url = versioned_reverse("event-list")
    response = api_client.post(create_url, minimal_event_dict, format="json")

    if is_external and (has_email or has_phone):
        assert response.status_code == status.HTTP_201_CREATED, str(response.content)
    elif is_external:
        assert "user_email" in response.json()
        assert "user_phone_number" in response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST, str(
            response.content
        )
    else:
        assert response.status_code == status.HTTP_201_CREATED, str(response.content)


@pytest.mark.parametrize("has_consent", [True, False])
@pytest.mark.parametrize("has_personal_information", [True, False])
@pytest.mark.django_db
def test_user_consent_is_required_for_personal_information_fields(
    api_client,
    minimal_event_dict,
    has_consent,
    has_personal_information,
):
    """Check that external user consent is required if personal information fields
    are filled.

    Admin users validate fields only when publishing, so consent not required on drafts.
    """
    minimal_event_dict["publication_status"] = "draft"
    del minimal_event_dict["publisher"]

    if has_consent:
        minimal_event_dict["user_consent"] = True
    if has_personal_information:
        minimal_event_dict["user_name"] = "User name"
        minimal_event_dict["maximum_attendee_capacity"] = 5
        minimal_event_dict["user_email"] = "email@example.com"
        minimal_event_dict["user_phone_number"] = "0501234567"
    user = UserFactory()
    api_client.force_authenticate(user=user)

    create_url = versioned_reverse("event-list")
    response = api_client.post(create_url, minimal_event_dict, format="json")

    if has_personal_information and not has_consent:
        assert "user_consent" in response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST, str(
            response.content
        )
    elif not has_personal_information:
        # External user needs to give personal information
        assert response.status_code == status.HTTP_400_BAD_REQUEST, str(
            response.content
        )
    else:
        assert response.status_code == status.HTTP_201_CREATED, str(response.content)
