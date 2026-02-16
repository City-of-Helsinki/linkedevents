import pytest
from rest_framework.exceptions import ValidationError

from registrations.serializers import SignUpGroupSerializer
from registrations.tests.factories import SignUpGroupFactory


@pytest.mark.django_db
def test_signup_group_serializer_validate_signups_existence():
    signup_group = SignUpGroupFactory()
    non_existent_signup_id = 99999
    serializer = SignUpGroupSerializer(
        instance=signup_group,
        data={
            "signups": [
                {
                    "id": non_existent_signup_id,
                    "first_name": "Ghost User 1",
                    "registration": signup_group.registration.pk,
                },
                {
                    "id": non_existent_signup_id + 1,
                    "first_name": "Ghost User 2",
                    "registration": signup_group.registration.pk,
                },
            ]
        },
        partial=True,
    )

    with pytest.raises(ValidationError) as excinfo:
        serializer.is_valid(raise_exception=True)

    assert "signups" in excinfo.value.detail
    assert (
        str(excinfo.value.detail["signups"][0])
        == f"Sign up with id: {non_existent_signup_id} doesn't exist."
    )
    assert (
        str(excinfo.value.detail["signups"][1])
        == f"Sign up with id: {non_existent_signup_id + 1} doesn't exist."
    )
