import pytest

from events.tests.utils import get, versioned_reverse
from helevents.tests.factories import UserFactory


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
