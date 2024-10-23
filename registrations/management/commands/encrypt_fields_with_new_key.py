from django.core.management import BaseCommand
from django.db import transaction

from registrations.models import SignUpGroupProtectedData, SignUpProtectedData


class Command(BaseCommand):
    help = (
        "Encrypts existing encrypted data with a new encryption key. Please remember to prepend "  # noqa: E501
        "the new key to the secrets value of the FIELD_ENCRYPTION_KEYS setting before running "  # noqa: E501
        "this command."
    )

    def handle(self, *args, **options):
        signup_group_protected_data = (
            SignUpGroupProtectedData.objects.select_for_update().all()
        )
        signup_protected_data = SignUpProtectedData.objects.select_for_update().all()

        group_update_fields = ["extra_info"]
        signup_update_fields = ["extra_info", "date_of_birth"]

        with transaction.atomic():
            for group_data in signup_group_protected_data:
                # Simply saving will cause the encrypted data to be fetched
                # and then saved with the new encryption key.
                group_data.save(update_fields=group_update_fields)

            for signup_data in signup_protected_data:
                signup_data.save(update_fields=signup_update_fields)
