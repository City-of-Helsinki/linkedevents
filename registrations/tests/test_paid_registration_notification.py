from decimal import Decimal

import pytest
import requests_mock
from django.conf import settings as django_settings
from django.core import mail
from django.test import override_settings
from rest_framework import status

from events.tests.factories import OrganizationFactory
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
    api_client,
    event,
):
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)
    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

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
        response = create_registration(api_client, registration_data)

    return response


@pytest.fixture
def financial_org():
    return OrganizationFactory(name="Financial org")


@pytest.fixture
def financial_admin(financial_org):
    financial_admin = UserFactory(email="financial_admin@hel.test")
    financial_org.financial_admin_users.add(financial_admin)

    return financial_admin


@pytest.fixture
def setup_parent_financial_organization_test(
    event, financial_org, financial_admin, settings
):
    parent_org = OrganizationFactory()
    financial_org.parent = parent_org
    financial_org.save()

    event.publisher.parent = financial_org
    event.publisher.save()

    settings.PAID_REGISTRATION_NOTIFICATION_ENABLED = True
    settings.PAID_REGISTRATION_NOTIFICATION_PARENT_ORGANIZATIONS = [parent_org.id]


@pytest.fixture
def assert_success(event, financial_admin, settings):
    def _assert_success(response):
        assert response.status_code == status.HTTP_201_CREATED
        assert len(mail.outbox) == 1

        email = mail.outbox[0]
        assert email.to == [financial_admin.email]
        assert "Uusi maksullinen ilmoittautuminen" in email.subject
        assert event.name_fi in email.subject

        html_message = str(email.alternatives[0])
        assert event.name_fi in html_message
        assert f"{settings.LINKED_EVENTS_UI_URL}/fi/registrations/" in html_message
        assert "Katso ilmoittautuminen" in html_message

    return _assert_success


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_sent_when_enabled_with_price_groups(
    assert_success, user, api_client, event, settings
):
    api_client.force_authenticate(user)

    response = create_registration_with_price_groups(
        api_client,
        event,
    )

    assert_success(response)


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_not_sent_when_setting_disabled(
    user, api_client, event, settings
):
    api_client.force_authenticate(user)

    settings.PAID_REGISTRATION_NOTIFICATION_ENABLED = False

    response = create_registration_with_price_groups(
        api_client,
        event,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_not_sent_without_price_groups(
    user, api_client, event
):
    api_client.force_authenticate(user)

    registration_data = get_minimal_required_registration_data(event.id)
    response = create_registration(api_client, registration_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_not_sent_without_financial_admins(
    user, api_client, event, financial_admin
):
    api_client.force_authenticate(user)
    financial_admin.delete()

    response = create_registration_with_price_groups(
        api_client,
        event,
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_not_sent_when_financial_admins_have_no_email(
    user, api_client, event, financial_admin
):
    api_client.force_authenticate(user)

    financial_admin.email = ""
    financial_admin.save()

    response = create_registration_with_price_groups(api_client, event)

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_sent_to_multiple_financial_admins(
    user, api_client, event, financial_admin, financial_org
):
    api_client.force_authenticate(user)

    financial_admin2 = UserFactory(email="financial_admin2@hel.test")
    financial_admin3 = UserFactory(email="financial_admin3@hel.test")

    financial_org.financial_admin_users.add(financial_admin2)
    financial_org.financial_admin_users.add(financial_admin3)

    response = create_registration_with_price_groups(
        api_client,
        event,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert set(email.to) == {
        financial_admin.email,
        financial_admin2.email,
        financial_admin3.email,
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_sent_to_admins_with_email_only(
    user, api_client, event, financial_admin, financial_org
):
    api_client.force_authenticate(user)

    financial_admin2 = UserFactory(email="")
    financial_admin3 = UserFactory(email="financial_admin3@hel.test")

    financial_org.financial_admin_users.add(financial_admin2)
    financial_org.financial_admin_users.add(financial_admin3)

    response = create_registration_with_price_groups(
        api_client,
        event,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert set(email.to) == {
        financial_admin.email,
        financial_admin3.email,
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_uses_finnish_event_name(
    user, api_client, event
):
    api_client.force_authenticate(user)

    event.name_fi = "Finnish Event Name"
    event.name_en = "English Event Name"
    event.name_sv = "Swedish Event Name"
    event.save()

    response = create_registration_with_price_groups(
        api_client,
        event,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert event.name_fi in email.subject

    html_message = str(email.alternatives[0])
    assert event.name_fi in html_message


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_sent_when_free_registration_updated_to_paid(
    user, api_client, event, financial_admin
):
    api_client.force_authenticate(user)

    registration = Registration.objects.create(
        event=event,
        created_by=user,
        last_modified_by=user,
    )

    default_price_group = PriceGroup.objects.filter(
        publisher=None, is_free=False
    ).first()

    update_url = reverse("registration-detail", kwargs={"pk": registration.pk})
    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    update_data = {
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
        response = api_client.patch(update_url, update_data, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert email.to == [financial_admin.email]
    assert "Uusi maksullinen ilmoittautuminen" in email.subject
    assert event.name_fi in email.subject


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_includes_registration_url(
    user, api_client, event, settings
):
    api_client.force_authenticate(user)

    response = create_registration_with_price_groups(api_client, event)

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    registration = Registration.objects.get(id=response.data["id"])
    email = mail.outbox[0]

    html_message = str(email.alternatives[0])
    expected_url = (
        f"{settings.LINKED_EVENTS_UI_URL}/fi/registrations/edit/{registration.id}"
    )
    assert expected_url in html_message


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_with_free_price_group_not_sent(
    user, api_client, event
):
    api_client.force_authenticate(user)

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        merchant = WebStoreMerchantFactory(organization=event.publisher)
    account = WebStoreAccountFactory(organization=event.publisher)

    free_price_group = PriceGroup.objects.filter(publisher=None, is_free=True).first()

    registration_data = {
        **get_minimal_required_registration_data(event.id),
        "registration_price_groups": [
            {
                "price_group": free_price_group.pk,
                "price": Decimal("0"),
                "vat_percentage": "0",
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
        response = create_registration(api_client, registration_data)

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_parent_financial_organization_test")
def test_paid_registration_notification_not_sent_when_paid_registration_updated(
    user, api_client, event, financial_admin
):
    api_client.force_authenticate(user)

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
        response = api_client.put(update_url, update_data, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_paid_registration_notification_not_sent_when_no_matching_organization(
    user, api_client, event, settings
):
    api_client.force_authenticate(user)

    # Create separate orgs for settings (but not in event hierarchy)
    parent_in_settings = OrganizationFactory()
    org_in_settings = OrganizationFactory()

    settings.PAID_REGISTRATION_NOTIFICATION_ENABLED = True
    settings.PAID_REGISTRATION_NOTIFICATION_PARENT_ORGANIZATIONS = [
        parent_in_settings.id
    ]
    settings.PAID_REGISTRATION_NOTIFICATION_ORGANIZATIONS = [org_in_settings.id]

    response = create_registration_with_price_groups(api_client, event)

    assert response.status_code == status.HTTP_201_CREATED
    # No email should be sent because no organization in the hierarchy matches
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_paid_registration_notification_not_sent_when_multiple_matching_organizations(
    user, api_client, event, sentry_init, sentry_capture_events, settings
):
    """Also test sentry events"""
    sentry_init()
    sentry_events = sentry_capture_events()

    api_client.force_authenticate(user)

    # Create hierarchy with multiple matching organizations
    grandparent = OrganizationFactory()
    parent = OrganizationFactory(parent=grandparent)
    event.publisher.parent = parent
    event.publisher.save()

    # Configure settings so both parent and grandparent match
    settings.PAID_REGISTRATION_NOTIFICATION_ENABLED = True
    settings.PAID_REGISTRATION_NOTIFICATION_PARENT_ORGANIZATIONS = []
    settings.PAID_REGISTRATION_NOTIFICATION_ORGANIZATIONS = [parent.id, grandparent.id]

    response = create_registration_with_price_groups(api_client, event)

    assert response.status_code == status.HTTP_201_CREATED
    # No email should be sent because multiple organizations match
    assert len(mail.outbox) == 0
    # Verify Sentry captured the MultipleObjectsReturned exception
    assert len(sentry_events) >= 1
    exception_events = [
        e
        for e in sentry_events
        if "exception" in e and "MultipleObjectsReturned" in str(e["exception"])
    ]
    assert len(exception_events) == 1


@pytest.mark.django_db
def test_paid_registration_notification_targets_correct_organization_in_hierarchy(
    user, api_client, event, settings
):
    """Test that notification is sent to the correct organization level in a multi-level hierarchy."""
    api_client.force_authenticate(user)

    # Create multi-level hierarchy: grandparent -> parent -> event.publisher
    grandparent = OrganizationFactory()
    parent = OrganizationFactory(parent=grandparent)
    event.publisher.parent = parent
    event.publisher.save()

    # Add financial admins to different levels
    grandparent_admin = UserFactory(email="grandparent_admin@hel.test")
    grandparent.financial_admin_users.add(grandparent_admin)

    parent_admin = UserFactory(email="parent_admin@hel.test")
    parent.financial_admin_users.add(parent_admin)

    publisher_admin = UserFactory(email="publisher_admin@hel.test")
    event.publisher.financial_admin_users.add(publisher_admin)

    # Configure to target only the parent organization
    settings.PAID_REGISTRATION_NOTIFICATION_ENABLED = True
    settings.PAID_REGISTRATION_NOTIFICATION_PARENT_ORGANIZATIONS = []
    settings.PAID_REGISTRATION_NOTIFICATION_ORGANIZATIONS = [parent.id]

    response = create_registration_with_price_groups(api_client, event)

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    # Only parent admin should receive the email
    assert email.to == [parent_admin.email]
    assert grandparent_admin.email not in email.to
    assert publisher_admin.email not in email.to


@pytest.mark.django_db
def test_paid_registration_notification_matches_by_parent_id(
    user, api_client, event, settings
):
    """Test that organizations can be matched by their parent's ID."""
    api_client.force_authenticate(user)

    # Create hierarchy: parent -> event.publisher
    parent = OrganizationFactory()
    event.publisher.parent = parent
    event.publisher.save()

    financial_admin = UserFactory(email="financial_admin@hel.test")
    event.publisher.financial_admin_users.add(financial_admin)

    # Match by parent ID (event.publisher has parent as parent)
    settings.PAID_REGISTRATION_NOTIFICATION_ENABLED = True
    settings.PAID_REGISTRATION_NOTIFICATION_PARENT_ORGANIZATIONS = [parent.id]
    settings.PAID_REGISTRATION_NOTIFICATION_ORGANIZATIONS = []

    response = create_registration_with_price_groups(api_client, event)

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mail.outbox) == 1

    email = mail.outbox[0]
    assert email.to == [financial_admin.email]
