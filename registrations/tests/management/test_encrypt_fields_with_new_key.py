import pytest
from django.core.management import call_command

from registrations.models import SignUpGroupProtectedData, SignUpProtectedData
from registrations.tests.factories import (
    SignUpFactory,
    SignUpGroupFactory,
    SignUpGroupProtectedDataFactory,
)

_ENCRYPTION_KEY = "c87a6669a1ded2834f1dfd0830d86ef6cdd20372ac83e8c7c23feffe87e6a051"
_ENCRYPTION_KEY2 = "f1a79d4b60a947b988beaf1eae871289fb03f2b9fd443d67107a7d05d05f831e"


@pytest.mark.django_db
def test_encrypt_fields_with_new_key(settings):
    old_keys = (_ENCRYPTION_KEY,)
    new_keys = (_ENCRYPTION_KEY2, _ENCRYPTION_KEY)
    settings.FIELD_ENCRYPTION_KEYS = old_keys

    signup_group_extra_info = "Signup group extra info"

    first_signup_extra_info = "First signup extra info"
    first_signup_dob = "2023-01-01"

    second_signup_extra_info = "Second signup extra info"
    second_signup_dob = "2023-02-02"

    signup_group = SignUpGroupFactory()
    signup_group_protected_data = SignUpGroupProtectedDataFactory(
        registration=signup_group.registration,
        signup_group=signup_group,
        extra_info=signup_group_extra_info,
    )

    first_signup = SignUpFactory(
        registration=signup_group.registration, signup_group=signup_group
    )
    first_signup_protected_data = SignUpProtectedData(
        registration=signup_group.registration,
        signup=first_signup,
        extra_info=first_signup_extra_info,
        date_of_birth=first_signup_dob,
    )

    second_signup = SignUpFactory(registration=signup_group.registration)
    second_signup_protected_data = SignUpProtectedData(
        registration=signup_group.registration,
        signup=second_signup,
        extra_info=second_signup_extra_info,
        date_of_birth=second_signup_dob,
    )

    def assert_encrypted_with_keys(keys):
        assert signup_group_protected_data.extra_info == signup_group_extra_info

        assert first_signup_protected_data.extra_info == first_signup_extra_info
        assert first_signup_protected_data.date_of_birth == first_signup_dob

        assert second_signup_protected_data.extra_info == second_signup_extra_info
        assert second_signup_protected_data.date_of_birth == second_signup_dob

        signup_group_extra_info_field = SignUpGroupProtectedData._meta.get_field(
            "extra_info"
        )
        assert signup_group_extra_info_field.keys == keys
        del signup_group_extra_info_field.keys

        signup_extra_info_field = SignUpProtectedData._meta.get_field("extra_info")
        assert signup_extra_info_field.keys == keys
        del signup_extra_info_field.keys

    # Test that fields have been encrypted with the old key
    assert_encrypted_with_keys(old_keys)

    settings.FIELD_ENCRYPTION_KEYS = new_keys
    call_command("encrypt_fields_with_new_key")

    # Test that fields have been encrypted with the new key
    assert_encrypted_with_keys(new_keys)
