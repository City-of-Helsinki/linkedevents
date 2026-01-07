from decimal import Decimal

import pytest
import requests_mock
from django.conf import settings as django_settings
from django.core import mail
from django.test import override_settings
from rest_framework import status

from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import PriceGroup, Registration
from registrations.tests.factories import (
    WebStoreAccountFactory,
    WebStoreMerchantFactory,
)
from registrations.tests.utils import (
    get_minimal_required_registration_data,
    get_registration_merchant_and_account_data,
)
from web_store.tests.product.test_web_store_product_api_client import (
    DEFAULT_GET_PRODUCT_MAPPING_DATA,
    DEFAULT_PRODUCT_ID,
)


def create_registration(api_client, registration_data):
    create_url = reverse("registration-list")
    response = api_client.post(create_url, registration_data, format="json")
    return response


def create_registration_with_price_groups(
    api_client, event, price_groups_data, financial_admins=None
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    if financial_admins:
        for admin in financial_admins:
            event.publisher.financial_admin_users.add(admin)

    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": price_groups_data,
        **get_registration_merchant_and_account_data(merchant, account),
    }

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )
        response = create_registration(api_client, registration_data)

    return response


@pytest.mark.django_db
def test_paid_registration_notification_sent_when_enabled_with_price_groups(
    user, api_client, event
):
    api_client.force_authenticate(user)

    financial_admin = UserFactory(email="financial@admin.com")

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    price_groups_data = [
        {
            "price_group": default_price_group.pk,
            "price": Decimal("10"),
            "vat_percentage": "25.5",
        }
    ]

    with override_settings(
        PAID_REGISTRATION_NOTIFICATION_ENABLED=True,
        LINKED_EVENTS_UI_URL="https://test.com",
    ):
        response = create_registration_with_price_groups(
            api_client, event, price_groups_data, [financial_admin]
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert email.to == ["financial@admin.com"]
    assert "Uusi maksullinen ilmoittautuminen" in email.subject
    assert event.name_fi in email.subject

    html_message = str(email.alternatives[0])
    assert event.name_fi in html_message
    assert "https://test.com/fi/registrations/" in html_message
    assert "Katso ilmoittautuminen" in html_message


@pytest.mark.django_db
def test_paid_registration_notification_not_sent_when_setting_disabled(
    user, api_client, event
):
    api_client.force_authenticate(user)

    financial_admin = UserFactory(email="financial@admin.com")

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    price_groups_data = [
        {
            "price_group": default_price_group.pk,
            "price": Decimal("10"),
            "vat_percentage": "25.5",
        }
    ]

    with override_settings(PAID_REGISTRATION_NOTIFICATION_ENABLED=False):
        response = create_registration_with_price_groups(
            api_client, event, price_groups_data, [financial_admin]
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_paid_registration_notification_not_sent_without_price_groups(
    user, api_client, event
):
    api_client.force_authenticate(user)

    financial_admin = UserFactory(email="financial@admin.com")
    event.publisher.financial_admin_users.add(financial_admin)

    registration_data = get_minimal_required_registration_data(event.id)

    with override_settings(PAID_REGISTRATION_NOTIFICATION_ENABLED=True):
        response = create_registration(api_client, registration_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_paid_registration_notification_not_sent_without_financial_admins(
    user, api_client, event
):
    api_client.force_authenticate(user)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    price_groups_data = [
        {
            "price_group": default_price_group.pk,
            "price": Decimal("10"),
            "vat_percentage": "25.5",
        }
    ]

    with override_settings(PAID_REGISTRATION_NOTIFICATION_ENABLED=True):
        response = create_registration_with_price_groups(
            api_client, event, price_groups_data, financial_admins=None
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_paid_registration_notification_not_sent_when_financial_admins_have_no_email(
    user, api_client, event
):
    api_client.force_authenticate(user)

    financial_admin = UserFactory(email="")

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    price_groups_data = [
        {
            "price_group": default_price_group.pk,
            "price": Decimal("10"),
            "vat_percentage": "25.5",
        }
    ]

    with override_settings(PAID_REGISTRATION_NOTIFICATION_ENABLED=True):
        response = create_registration_with_price_groups(
            api_client, event, price_groups_data, [financial_admin]
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_paid_registration_notification_sent_to_multiple_financial_admins(
    user, api_client, event
):
    api_client.force_authenticate(user)

    financial_admin1 = UserFactory(email="financial1@admin.com")
    financial_admin2 = UserFactory(email="financial2@admin.com")
    financial_admin3 = UserFactory(email="financial3@admin.com")

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    price_groups_data = [
        {
            "price_group": default_price_group.pk,
            "price": Decimal("10"),
            "vat_percentage": "25.5",
        }
    ]

    with override_settings(
        PAID_REGISTRATION_NOTIFICATION_ENABLED=True,
        LINKED_EVENTS_UI_URL="https://test.com",
    ):
        response = create_registration_with_price_groups(
            api_client,
            event,
            price_groups_data,
            [financial_admin1, financial_admin2, financial_admin3],
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert set(email.to) == {
        "financial1@admin.com",
        "financial2@admin.com",
        "financial3@admin.com",
    }


@pytest.mark.django_db
def test_paid_registration_notification_sent_to_admins_with_email_only(
    user, api_client, event
):
    api_client.force_authenticate(user)

    financial_admin1 = UserFactory(email="financial1@admin.com")
    financial_admin2 = UserFactory(email="")
    financial_admin3 = UserFactory(email="financial3@admin.com")

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    price_groups_data = [
        {
            "price_group": default_price_group.pk,
            "price": Decimal("10"),
            "vat_percentage": "25.5",
        }
    ]

    with override_settings(
        PAID_REGISTRATION_NOTIFICATION_ENABLED=True,
        LINKED_EVENTS_UI_URL="https://test.com",
    ):
        response = create_registration_with_price_groups(
            api_client,
            event,
            price_groups_data,
            [financial_admin1, financial_admin2, financial_admin3],
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert set(email.to) == {"financial1@admin.com", "financial3@admin.com"}


@pytest.mark.django_db
def test_paid_registration_notification_uses_finnish_event_name(
    user, api_client, event
):
    api_client.force_authenticate(user)

    event.name_fi = "Finnish Event Name"
    event.name_en = "English Event Name"
    event.name_sv = "Swedish Event Name"
    event.save()

    financial_admin = UserFactory(email="financial@admin.com")

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    price_groups_data = [
        {
            "price_group": default_price_group.pk,
            "price": Decimal("10"),
            "vat_percentage": "25.5",
        }
    ]

    with override_settings(
        PAID_REGISTRATION_NOTIFICATION_ENABLED=True,
        LINKED_EVENTS_UI_URL="https://test.com",
    ):
        response = create_registration_with_price_groups(
            api_client, event, price_groups_data, [financial_admin]
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert "Finnish Event Name" in email.subject

    html_message = str(email.alternatives[0])
    assert "Finnish Event Name" in html_message


@pytest.mark.django_db
def test_paid_registration_notification_sent_when_free_registration_updated_to_paid(
    user, api_client, event
):
    api_client.force_authenticate(user)

    financial_admin = UserFactory(email="financial@admin.com")
    event.publisher.financial_admin_users.add(financial_admin)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    registration = Registration.objects.create(
        event=event,
        created_by=user,
        last_modified_by=user,
    )

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    update_url = reverse("registration-detail", kwargs={"pk": registration.pk})
    update_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": "25.5",
            }
        ],
        **get_registration_merchant_and_account_data(merchant, account),
    }

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        with override_settings(
            PAID_REGISTRATION_NOTIFICATION_ENABLED=True,
            LINKED_EVENTS_UI_URL="https://test.com",
        ):
            response = api_client.put(update_url, update_data, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert email.to == ["financial@admin.com"]
    assert "Uusi maksullinen ilmoittautuminen" in email.subject
    assert event.name_fi in email.subject


@pytest.mark.django_db
def test_paid_registration_notification_includes_registration_url(
    user, api_client, event
):
    api_client.force_authenticate(user)

    financial_admin = UserFactory(email="financial@admin.com")

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    price_groups_data = [
        {
            "price_group": default_price_group.pk,
            "price": Decimal("10"),
            "vat_percentage": "25.5",
        }
    ]

    with override_settings(
        PAID_REGISTRATION_NOTIFICATION_ENABLED=True,
        LINKED_EVENTS_UI_URL="https://test.com",
    ):
        response = create_registration_with_price_groups(
            api_client, event, price_groups_data, [financial_admin]
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    registration = Registration.objects.get(id=response.data["id"])
    email = mail.outbox[0]

    html_message = str(email.alternatives[0])
    expected_url = f"https://test.com/fi/registrations/edit/{registration.id}"
    assert expected_url in html_message


@pytest.mark.django_db
def test_paid_registration_notification_with_free_price_group_not_sent(
    user, api_client, event
):
    api_client.force_authenticate(user)

    financial_admin = UserFactory(email="financial@admin.com")

    free_price_group = PriceGroup.objects.filter(publisher=None, is_free=True).first()

    price_groups_data = [
        {
            "price_group": free_price_group.pk,
            "price": Decimal("0"),
            "vat_percentage": "0",
        }
    ]

    with override_settings(PAID_REGISTRATION_NOTIFICATION_ENABLED=True):
        response = create_registration_with_price_groups(
            api_client, event, price_groups_data, [financial_admin]
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_paid_registration_notification_not_sent_when_paid_registration_updated(
    user, api_client, event
):
    api_client.force_authenticate(user)

    financial_admin = UserFactory(email="financial@admin.com")
    event.publisher.financial_admin_users.add(financial_admin)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    # First create a paid registration
    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("10"),
                "vat_percentage": "25.5",
            }
        ],
        **get_registration_merchant_and_account_data(merchant, account),
    }

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        with override_settings(PAID_REGISTRATION_NOTIFICATION_ENABLED=True):
            create_response = create_registration(api_client, registration_data)

    assert create_response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    # Clear mail outbox
    mail.outbox = []

    # Now update the registration (e.g., change price)
    registration = Registration.objects.get(id=create_response.data["id"])
    update_url = reverse("registration-detail", kwargs={"pk": registration.pk})
    update_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [
            {
                "price_group": default_price_group.pk,
                "price": Decimal("15"),  # Changed price
                "vat_percentage": "25.5",
            }
        ],
        **get_registration_merchant_and_account_data(merchant, account),
    }

    with requests_mock.Mocker() as req_mock:
        base_url = f"{django_settings.WEB_STORE_API_BASE_URL}product/"
        req_mock.post(base_url, json=DEFAULT_GET_PRODUCT_MAPPING_DATA)
        req_mock.post(
            f"{base_url}{DEFAULT_PRODUCT_ID}/accounting",
            json=DEFAULT_GET_PRODUCT_MAPPING_DATA,
        )

        with override_settings(PAID_REGISTRATION_NOTIFICATION_ENABLED=True):
            response = api_client.put(update_url, update_data, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == 0
