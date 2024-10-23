from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from typing import Optional
from unittest.mock import PropertyMock, patch

import pytest
import requests_mock
from django.conf import settings
from django.core import mail
from django.test import override_settings
from django.utils import translation
from django.utils.timezone import localtime
from freezegun import freeze_time
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event
from events.tests.factories import LanguageFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import (
    SignUp,
    SignUpContactPerson,
    SignUpPayment,
    SignUpPaymentCancellation,
    SignUpPaymentRefund,
    SignUpPriceGroup,
)
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationPriceGroupFactory,
    RegistrationUserAccessFactory,
    RegistrationWebStoreProductMappingFactory,
    SeatReservationCodeFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpPaymentCancellationFactory,
    SignUpPaymentFactory,
    SignUpPaymentRefundFactory,
    SignUpPriceGroupFactory,
)
from registrations.tests.test_registration_post import hel_email
from registrations.tests.test_signup_post import assert_create_signups
from registrations.tests.utils import (
    assert_payment_link_email_sent,
    create_price_group,
    create_signup_group_with_payment,
    create_user_by_role,
    update_price_group_price,
)
from web_store.tests.order.test_web_store_order_api_client import (
    DEFAULT_CANCEL_ORDER_DATA,
    DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE,
    DEFAULT_GET_ORDER_DATA,
    DEFAULT_ORDER_ID,
)
from web_store.tests.payment.test_web_store_payment_api_client import (
    DEFAULT_GET_PAYMENT_DATA,
    DEFAULT_REFUND_ID,
)

_PARTIAL_REFUND_AMOUNT = Decimal("5")

# === util methods ===


def delete_signup(api_client, signup_pk, query_string=None):
    signup_url = reverse(
        "signup-detail",
        kwargs={"pk": signup_pk},
    )
    if query_string:
        signup_url = "%s?%s" % (signup_url, query_string)

    return api_client.delete(signup_url)


def assert_delete_signup(
    api_client,
    signup_pk,
    query_string=None,
    signup_count=1,
    contact_person_count: Optional[int] = 1,
):
    assert SignUp.objects.count() == signup_count

    if contact_person_count is not None:
        assert SignUpContactPerson.objects.count() == contact_person_count

    response = delete_signup(api_client, signup_pk, query_string)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert SignUp.objects.count() == (signup_count - 1 if signup_count else 0)

    if contact_person_count is not None:
        assert SignUpContactPerson.objects.count() == (
            contact_person_count - 1 if contact_person_count else 0
        )


def assert_delete_signup_failed(
    api_client,
    signup_pk,
    status_code=status.HTTP_403_FORBIDDEN,
    signup_count=1,
    contact_person_count=1,
):
    assert SignUp.objects.count() == signup_count
    assert SignUpContactPerson.objects.count() == contact_person_count

    response = delete_signup(api_client, signup_pk)
    assert response.status_code == status_code

    assert SignUp.objects.count() == signup_count
    assert SignUpContactPerson.objects.count() == contact_person_count


# === tests ===


@pytest.mark.parametrize("user_role", ["admin", "registration_admin"])
@pytest.mark.django_db
def test_registration_admin_or_registration_created_admin_can_delete_signup(
    registration, signup, api_client, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    if user_role == "admin":
        registration.created_by = user
        registration.save(update_fields=["created_by"])

    assert_delete_signup(api_client, signup.id)


@pytest.mark.parametrize(
    "user_role", ["admin", "financial_admin", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_created_by_financial_admin_or_regular_user_can_delete_signup(
    registration, signup, api_client, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup.created_by = user
    signup.save(update_fields=["created_by"])

    assert_delete_signup(api_client, signup.id)


@pytest.mark.parametrize("user_role", ["admin", "financial_admin", "regular_user"])
@pytest.mark.django_db
def test_non_created_user_or_admin_or_financial_admin_cannot_delete_signup(
    registration, signup, user2, api_client, user_role
):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    registration.created_by = user2
    registration.save(update_fields=["created_by"])

    assert_delete_signup_failed(api_client, signup.id)


@pytest.mark.django_db
def test_contact_person_can_delete_signup_when_strongly_identified(
    api_client, registration
):
    user = create_user_by_role("regular_user", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup, user=user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=["suomi_fi"],
    ) as mocked:
        assert_delete_signup(api_client, signup.id)
        assert mocked.called is True


@pytest.mark.django_db
def test_contact_person_cannot_delete_signup_when_not_strongly_identified(
    api_client, registration
):
    user = create_user_by_role("regular_user", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=signup, user=user)

    with patch(
        "helevents.models.UserModelPermissionMixin.token_amr_claim",
        new_callable=PropertyMock,
        return_value=[],
    ) as mocked:
        response = delete_signup(api_client, signup.id)
        assert mocked.called is True
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    "username,service_language,expected_subject,expected_heading,expected_text",
    [
        (
            "Username",
            "en",
            "Registration cancelled",
            "Username, registration to the event Foo has been cancelled.",
            "You have successfully cancelled your registration to the event <strong>Foo</strong>.",
        ),
        (
            "Käyttäjänimi",
            "fi",
            "Ilmoittautuminen peruttu",
            "Käyttäjänimi, ilmoittautuminen tapahtumaan Foo on peruttu.",
            "Olet onnistuneesti peruuttanut ilmoittautumisesi tapahtumaan <strong>Foo</strong>.",
        ),
        (
            "Användarnamn",
            "sv",
            "Registreringen avbruten",
            "Användarnamn, anmälan till evenemanget Foo har ställts in.",
            "Du har avbrutit din registrering till evenemanget <strong>Foo</strong>.",
        ),
        (
            None,
            "en",
            "Registration cancelled",
            "Registration to the event Foo has been cancelled.",
            "You have successfully cancelled your registration to the event <strong>Foo</strong>.",
        ),
        (
            None,
            "fi",
            "Ilmoittautuminen peruttu",
            "Ilmoittautuminen tapahtumaan Foo on peruttu.",
            "Olet onnistuneesti peruuttanut ilmoittautumisesi tapahtumaan <strong>Foo</strong>.",
        ),
        (
            None,
            "sv",
            "Registreringen avbruten",
            "Anmälan till evenemanget Foo har ställts in.",
            "Du har avbrutit din registrering till evenemanget <strong>Foo</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_email_sent_on_successful_signup_deletion(
    expected_heading,
    expected_subject,
    expected_text,
    registration,
    username,
    service_language,
    signup,
    api_client,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup.contact_person.first_name = username
    signup.contact_person.service_language = LanguageFactory(
        pk=service_language, service_language=True
    )
    signup.contact_person.save(update_fields=["first_name", "service_language"])

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()

        assert_delete_signup(api_client, signup.id)
        #  assert that the email was sent
        assert mail.outbox[0].subject.startswith(expected_subject)
        assert expected_heading in str(mail.outbox[0].alternatives[0])
        assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "username,service_language,expected_subject,expected_heading,expected_text",
    [
        (
            "Username",
            "en",
            "Registration cancelled - Recurring: Foo",
            "Username, registration to the recurring event Foo 1 Feb 2024 - 29 Feb 2024 has been "
            "cancelled.",
            "You have successfully cancelled your registration to the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong>.",
        ),
        (
            "Käyttäjänimi",
            "fi",
            "Ilmoittautuminen peruttu - Sarja: Foo",
            "Käyttäjänimi, ilmoittautuminen sarjatapahtumaan Foo 1.2.2024 - 29.2.2024 on peruttu.",
            "Olet onnistuneesti peruuttanut ilmoittautumisesi sarjatapahtumaan "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>.",
        ),
        (
            "Användarnamn",
            "sv",
            "Registreringen avbruten - Serie: Foo",
            "Användarnamn, anmälan till serieevenemanget Foo 1.2.2024 - 29.2.2024 har ställts in.",
            "Du har avbrutit din registrering till serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>.",
        ),
        (
            None,
            "en",
            "Registration cancelled - Recurring: Foo",
            "Registration to the recurring event Foo 1 Feb 2024 - 29 Feb 2024 has been cancelled.",
            "You have successfully cancelled your registration to the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong>.",
        ),
        (
            None,
            "fi",
            "Ilmoittautuminen peruttu - Sarja: Foo",
            "Ilmoittautuminen sarjatapahtumaan Foo 1.2.2024 - 29.2.2024 on peruttu.",
            "Olet onnistuneesti peruuttanut ilmoittautumisesi sarjatapahtumaan "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>.",
        ),
        (
            None,
            "sv",
            "Registreringen avbruten - Serie: Foo",
            "Anmälan till serieevenemanget Foo 1.2.2024 - 29.2.2024 har ställts in.",
            "Du har avbrutit din registrering till serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong>.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_email_sent_on_successful_signup_deletion_for_recurring_event(
    api_client,
    username,
    service_language,
    expected_heading,
    expected_subject,
    expected_text,
):
    lang = LanguageFactory(pk=service_language, service_language=True)

    with translation.override(service_language):
        now = localtime()
        registration = RegistrationFactory(
            event__start_time=now,
            event__end_time=now + timedelta(days=28),
            event__super_event_type=Event.SuperEventType.RECURRING,
            event__name="Foo",
        )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(
        signup=signup, first_name=username, service_language=lang, email="test@test.com"
    )

    with translation.override(service_language):
        assert_delete_signup(api_client, signup.id)

    #  assert that the email was sent
    message_html_string = str(mail.outbox[0].alternatives[0])
    assert mail.outbox[0].subject.startswith(expected_subject)
    assert expected_heading in message_html_string
    assert expected_text in message_html_string


@pytest.mark.parametrize(
    "event_type,expected_heading,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "Username, registration to the event Foo has been cancelled.",
            "You have successfully cancelled your registration to the event <strong>Foo</strong>.",
        ),
        (
            Event.TypeId.COURSE,
            "Username, registration to the course Foo has been cancelled.",
            "You have successfully cancelled your registration to the course <strong>Foo</strong>.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "Username, registration to the volunteering Foo has been cancelled.",
            "You have successfully cancelled your registration to the volunteering <strong>Foo</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_cancellation_confirmation_template_has_correct_text_per_event_type(
    event_type,
    expected_heading,
    expected_text,
    registration,
    signup,
    api_client,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup.contact_person.first_name = "Username"
    signup.contact_person.service_language = LanguageFactory(
        pk="en", service_language=True
    )
    signup.contact_person.save(update_fields=["first_name", "service_language"])

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()

    assert_delete_signup(api_client, signup.id)
    #  assert that the email was sent
    assert len(mail.outbox) == 1
    assert expected_heading in str(mail.outbox[0].alternatives[0])
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "event_type,expected_heading,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "Username, registration to the recurring event Foo 1 Feb 2024 - 29 Feb 2024 "
            "has been cancelled.",
            "You have successfully cancelled your registration to the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong>.",
        ),
        (
            Event.TypeId.COURSE,
            "Username, registration to the recurring course Foo 1 Feb 2024 - 29 Feb 2024 "
            "has been cancelled.",
            "You have successfully cancelled your registration to the recurring course "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong>.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "Username, registration to the recurring volunteering Foo 1 Feb 2024 - 29 Feb 2024 "
            "has been cancelled.",
            "You have successfully cancelled your registration to the recurring volunteering "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong>.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_cancellation_confirmation_template_has_correct_text_per_event_type_for_a_recurring_event(
    api_client,
    event_type,
    expected_heading,
    expected_text,
):
    lang = LanguageFactory(pk="en", service_language=True)

    now = localtime()
    registration = RegistrationFactory(
        event__start_time=now,
        event__end_time=now + timedelta(days=28),
        event__super_event_type=Event.SuperEventType.RECURRING,
        event__type_id=event_type,
        event__name="Foo",
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(
        signup=signup,
        first_name="Username",
        service_language=lang,
        email="test@test.com",
    )

    assert_delete_signup(api_client, signup.id)

    #  assert that the email was sent
    message_html_string = str(mail.outbox[0].alternatives[0])
    assert len(mail.outbox) == 1
    assert expected_heading in message_html_string
    assert expected_text in message_html_string


@pytest.mark.django_db
def test_cannot_delete_already_deleted_signup(signup, api_client):
    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert_delete_signup(api_client, signup.id)
    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_registration_user_access_cannot_delete_signup(
    registration, signup, api_client
):
    user = create_user_by_role("regular_user", signup.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(registration=registration, email=user.email)

    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_registration_substitute_user_delete_signup(registration, signup, api_client):
    user = UserFactory(email=hel_email)
    user.organization_memberships.add(signup.publisher)
    api_client.force_authenticate(user)

    RegistrationUserAccessFactory(
        registration=registration,
        email=user.email,
        is_substitute_user=True,
    )

    assert_delete_signup(api_client, signup.id)


@pytest.mark.django_db
def test_not_created_user_without_organization_cannot_delete_signup(api_client, signup):
    user = UserFactory()
    api_client.force_authenticate(user)

    assert_delete_signup_failed(api_client, signup.id)


@pytest.mark.django_db
def test_created_user_without_organization_can_delete_signup(api_client, signup):
    user = UserFactory()
    api_client.force_authenticate(user)

    signup.created_by = user
    signup.save(update_fields=["created_by"])

    assert_delete_signup(api_client, signup.id)


@pytest.mark.django_db
def test_not_authenticated_user_cannot_delete_signup(api_client, signup):
    assert_delete_signup_failed(
        api_client, signup.id, status_code=status.HTTP_401_UNAUTHORIZED
    )


@pytest.mark.django_db
def test_api_key_with_organization_can_delete_signup(
    api_client, data_source, organization, signup
):
    data_source.user_editable_registrations = True
    data_source.owner = organization
    data_source.save(update_fields=["user_editable_registrations", "owner"])
    api_client.credentials(apikey=data_source.api_key)

    assert_delete_signup(api_client, signup.id)


@pytest.mark.django_db
def test_api_key_of_other_organization_cannot_delete_signup(
    api_client, data_source, organization2, signup
):
    data_source.owner = organization2
    data_source.save()
    api_client.credentials(apikey=data_source.api_key)

    assert_delete_signup_failed(api_client, signup.id)


@pytest.mark.django_db
def test_api_key_from_wrong_data_source_cannot_delete_signup(
    api_client, organization, other_data_source, signup
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    assert_delete_signup_failed(api_client, signup.id)


@pytest.mark.parametrize("api_key", ["", "unknown"])
@pytest.mark.django_db
def test_invalid_api_key_cannot_delete_signup(api_client, signup, api_key):
    api_client.credentials(apikey=api_key)

    assert_delete_signup_failed(
        api_client, signup.id, status_code=status.HTTP_401_UNAUTHORIZED
    )


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.django_db
def test_registration_admin_can_delete_signup_regardless_of_non_user_editable_resources(
    data_source, organization, signup, api_client, user_editable_resources
):
    user = create_user_by_role("registration_admin", organization)
    api_client.force_authenticate(user)

    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    assert_delete_signup(api_client, signup.id)


@pytest.mark.parametrize(
    "attendee_status",
    [
        SignUp.AttendeeStatus.ATTENDING,
        SignUp.AttendeeStatus.WAITING_LIST,
    ],
)
@pytest.mark.django_db
def test_signup_deletion_leads_to_changing_status_of_first_waitlisted_user(
    api_client, registration, attendee_status
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration.maximum_attendee_capacity = 1
    registration.save(update_fields=["maximum_attendee_capacity"])

    reservation = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data = {
        "name": "Michael Jackson1",
        "attendee_status": attendee_status,
        "contact_person": {
            "email": "test@test.com",
        },
    }
    signups_data = {
        "registration": registration.id,
        "reservation_code": reservation.code,
        "signups": [signup_data],
    }
    response = assert_create_signups(api_client, signups_data)
    signup_id = response.data[0]["id"]

    reservation2 = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data2 = {
        "name": "Michael Jackson2",
        "attendee_status": SignUp.AttendeeStatus.WAITING_LIST,
        "contact_person": {
            "email": "test1@test.com",
        },
    }
    signups_data2 = {
        "registration": registration.id,
        "reservation_code": reservation2.code,
        "signups": [signup_data2],
    }
    assert_create_signups(api_client, signups_data2)

    reservation3 = SeatReservationCodeFactory(registration=registration, seats=1)
    signup_data3 = {
        "name": "Michael Jackson3",
        "attendee_status": SignUp.AttendeeStatus.WAITING_LIST,
        "contact_person": {
            "email": "test2@test.com",
        },
    }
    signups_data3 = {
        "registration": registration.id,
        "reservation_code": reservation3.code,
        "signups": [signup_data3],
    }
    assert_create_signups(api_client, signups_data3)

    assert (
        SignUp.objects.get(
            contact_person__email=signup_data["contact_person"]["email"]
        ).attendee_status
        == attendee_status
    )
    assert (
        SignUp.objects.get(
            contact_person__email=signup_data2["contact_person"]["email"]
        ).attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )
    assert (
        SignUp.objects.get(
            contact_person__email=signup_data3["contact_person"]["email"]
        ).attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )

    assert_delete_signup(api_client, signup_id, signup_count=3, contact_person_count=3)
    assert (
        SignUp.objects.get(
            contact_person__email=signup_data2["contact_person"]["email"]
        ).attendee_status
        == attendee_status
    )
    assert (
        SignUp.objects.get(
            contact_person__email=signup_data3["contact_person"]["email"]
        ).attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_text",
    [
        (
            "en",
            "Registration confirmation",
            "You have been moved from the waiting list of the event <strong>Foo</strong> to a participant.",
        ),
        (
            "fi",
            "Vahvistus ilmoittautumisesta",
            "Sinut on siirretty tapahtuman <strong>Foo</strong> jonotuslistalta osallistujaksi.",
        ),
        (
            "sv",
            "Bekräftelse av registrering",
            "Du har flyttats från väntelistan för evenemanget <strong>Foo</strong> till en deltagare.",
        ),
    ],
)
@pytest.mark.django_db
def test_send_email_when_moving_participant_from_waitlist(
    api_client,
    expected_subject,
    expected_text,
    registration,
    service_language,
    signup,
    signup2,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    language = LanguageFactory(pk=service_language, service_language=True)

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()
        registration.maximum_attendee_capacity = 1
        registration.save()

        signup.attendee_status = SignUp.AttendeeStatus.ATTENDING
        signup.save(update_fields=["attendee_status"])

        signup2.attendee_status = SignUp.AttendeeStatus.WAITING_LIST
        signup2.save(update_fields=["attendee_status"])

        signup2.contact_person.service_language = language
        signup2.contact_person.save(update_fields=["service_language"])

        assert_delete_signup(
            api_client, signup.id, signup_count=2, contact_person_count=2
        )

        # Signup 2 status should be changed
        assert (
            SignUp.objects.get(pk=signup2.pk).attendee_status
            == SignUp.AttendeeStatus.ATTENDING
        )
        # Send email to signup who is transferred as participant
        assert mail.outbox[0].subject.startswith(expected_subject)
        assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_text",
    [
        (
            "en",
            "Registration confirmation - Recurring: Foo",
            "You have been moved from the waiting list of the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> to a participant.",
        ),
        (
            "fi",
            "Vahvistus ilmoittautumisesta - Sarja: Foo",
            "Sinut on siirretty sarjatapahtuman "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong> jonotuslistalta osallistujaksi.",
        ),
        (
            "sv",
            "Bekräftelse av registrering - Serie: Foo",
            "Du har flyttats från väntelistan för serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong> till en deltagare.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_send_email_when_moving_participant_from_waitlist_for_a_recurring_event(
    api_client,
    service_language,
    expected_subject,
    expected_text,
):
    lang = LanguageFactory(pk=service_language, service_language=True)

    with translation.override(service_language):
        now = localtime()
        registration = RegistrationFactory(
            event__start_time=now,
            event__end_time=now + timedelta(days=28),
            event__super_event_type=Event.SuperEventType.RECURRING,
            event__name="Foo",
            maximum_attendee_capacity=1,
        )

    signup = SignUpFactory(
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    SignUpContactPersonFactory(signup=signup, service_language=lang)

    signup2 = SignUpFactory(
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
    )
    SignUpContactPersonFactory(
        signup=signup2, service_language=lang, email="test@test.com"
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    with translation.override(service_language):
        assert_delete_signup(
            api_client, signup.id, signup_count=2, contact_person_count=2
        )

    # Signup 2 status should be changed
    signup2.refresh_from_db()
    assert signup2.attendee_status == SignUp.AttendeeStatus.ATTENDING

    # Send email to signup who is transferred as participant
    assert mail.outbox[0].subject.startswith(expected_subject)
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_group_contact_person_gets_waitlisted_to_participant_transfer_email(
    api_client, registration
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    language = LanguageFactory(pk="fi", service_language=True)
    with translation.override(language.pk):
        registration.event.name = "Foo"
        registration.event.save()

    attending_signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=attending_signup, email="test@test.com")

    waitlisted_group = SignUpGroupFactory(registration=registration)
    waitlisted_signup = SignUpFactory(
        registration=registration,
        signup_group=waitlisted_group,
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
    )
    waitlisted_contact_person = SignUpContactPersonFactory(
        signup_group=waitlisted_group, email="test2@test.com"
    )

    assert waitlisted_signup.attendee_status == SignUp.AttendeeStatus.WAITING_LIST

    assert_delete_signup(
        api_client, attending_signup.id, signup_count=2, contact_person_count=2
    )

    waitlisted_signup.refresh_from_db()
    assert waitlisted_signup.attendee_status == SignUp.AttendeeStatus.ATTENDING

    assert len(mail.outbox[0].to) == 1
    assert waitlisted_contact_person.email in mail.outbox[0].to
    assert mail.outbox[0].subject.startswith("Vahvistus ilmoittautumisesta")
    assert (
        "Sinut on siirretty tapahtuman <strong>Foo</strong> jonotuslistalta osallistujaksi."
        in str(mail.outbox[0].alternatives[0])
    )


@pytest.mark.parametrize(
    "event_type,expected_subject,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "Registration confirmation",
            "You have been moved from the waiting list of the event <strong>Foo</strong> to a participant.",
        ),
        (
            Event.TypeId.COURSE,
            "Registration confirmation",
            "You have been moved from the waiting list of the course <strong>Foo</strong> to a participant.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "Registration confirmation",
            "You have been moved from the waiting list of the volunteering <strong>Foo</strong> to a participant.",
        ),
    ],
)
@pytest.mark.django_db
def test_transferred_as_participant_template_has_correct_text_per_event_type(
    api_client,
    event_type,
    expected_subject,
    expected_text,
    registration,
    signup,
    signup2,
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()

    registration.maximum_attendee_capacity = 1
    registration.save(update_fields=["maximum_attendee_capacity"])

    signup.attendee_status = SignUp.AttendeeStatus.ATTENDING
    signup.save(update_fields=["attendee_status"])

    signup2.attendee_status = SignUp.AttendeeStatus.WAITING_LIST
    signup2.save(update_fields=["attendee_status"])

    signup2.contact_person.service_language = LanguageFactory(
        pk="en", service_language=True
    )
    signup2.contact_person.save(update_fields=["service_language"])

    assert_delete_signup(api_client, signup.id, signup_count=2, contact_person_count=2)

    # Signup 2 status should be changed
    assert (
        SignUp.objects.get(pk=signup2.pk).attendee_status
        == SignUp.AttendeeStatus.ATTENDING
    )
    # Send email to signup who is transferred as participant
    assert mail.outbox[0].subject.startswith(expected_subject)
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "event_type,expected_subject,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "Registration confirmation - Recurring: Foo",
            "You have been moved from the waiting list of the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> to a participant.",
        ),
        (
            Event.TypeId.COURSE,
            "Registration confirmation - Recurring: Foo",
            "You have been moved from the waiting list of the recurring course "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> to a participant.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "Registration confirmation - Recurring: Foo",
            "You have been moved from the waiting list of the recurring volunteering "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> to a participant.",
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_transferred_as_participant_has_correct_text_per_event_type_for_a_recurring_event(
    api_client,
    event_type,
    expected_subject,
    expected_text,
):
    lang = LanguageFactory(pk="en", service_language=True)

    now = localtime()
    registration = RegistrationFactory(
        event__start_time=now,
        event__end_time=now + timedelta(days=28),
        event__super_event_type=Event.SuperEventType.RECURRING,
        event__name="Foo",
        maximum_attendee_capacity=1,
        event__type_id=event_type,
    )

    signup = SignUpFactory(
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    SignUpContactPersonFactory(signup=signup, service_language=lang)

    signup2 = SignUpFactory(
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
    )
    SignUpContactPersonFactory(
        signup=signup2, service_language=lang, email="test@test.com"
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    assert_delete_signup(api_client, signup.id, signup_count=2, contact_person_count=2)

    # Signup 2 status should be changed
    signup2.refresh_from_db()
    assert signup2.attendee_status == SignUp.AttendeeStatus.ATTENDING

    # Send email to signup who is transferred as participant
    assert mail.outbox[0].subject.startswith(expected_subject)
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_delete_signup_from_group(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(registration=registration, signup_group=signup_group)
    signup = SignUpFactory(registration=registration, signup_group=signup_group)

    assert SignUp.objects.count() == 2

    response = delete_signup(api_client, signup.pk)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert SignUp.objects.count() == 1


@pytest.mark.django_db
def test_signup_id_is_audit_logged_on_delete(api_client, signup):
    user = UserFactory()
    user.registration_admin_organizations.add(signup.publisher)
    api_client.force_authenticate(user)

    assert_delete_signup(api_client, signup.pk)

    audit_log_entry = AuditLogEntry.objects.first()
    assert audit_log_entry.message["audit_event"]["target"]["object_ids"] == [signup.pk]


@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "regular_user"]
)
@pytest.mark.django_db
def test_signup_price_group_deleted_with_signup(api_client, registration, user_role):
    user = create_user_by_role(user_role, registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration=registration,
        created_by=user if user_role == "regular_user" else None,
    )
    SignUpPriceGroupFactory(signup=signup)

    assert SignUpPriceGroup.objects.count() == 1

    assert_delete_signup(api_client, signup.id, contact_person_count=0)

    assert SignUpPriceGroup.objects.count() == 0


@pytest.mark.django_db
def test_cannot_delete_soft_deleted_signup(api_client, registration):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    soft_deleted_signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(signup=soft_deleted_signup, email="test2@test.com")
    soft_deleted_signup.soft_delete()

    assert SignUp.all_objects.count() == 1

    response = delete_signup(api_client, soft_deleted_signup.pk)
    assert response.status_code == status.HTTP_404_NOT_FOUND

    assert SignUp.all_objects.count() == 1

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_soft_deleted_signup_is_not_moved_to_attending_from_waiting_list(
    api_client, registration
):
    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )
    SignUpContactPersonFactory(signup=signup, email="test@test.com")

    soft_deleted_signup = SignUpFactory(
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
    )
    SignUpContactPersonFactory(signup=soft_deleted_signup, email="test2@test.com")
    soft_deleted_signup.soft_delete()

    assert_delete_signup(api_client, signup.id, signup_count=1, contact_person_count=1)

    soft_deleted_signup.refresh_from_db()
    assert soft_deleted_signup.attendee_status == SignUp.AttendeeStatus.WAITING_LIST

    # The deleted signup will get a cancellation email, but the soft deleted one will not get any.
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject.startswith("Ilmoittautuminen peruttu")


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_text",
    [
        (
            "en",
            "Payment required for registration confirmation - Foo",
            "You have been selected to be moved from the waiting list of the event "
            "<strong>Foo</strong> to a participant. Please use the "
            "payment link to confirm your participation. The payment link expires in "
            "%(hours)s hours" % {"hours": settings.WEB_STORE_ORDER_EXPIRATION_HOURS},
        ),
        (
            "fi",
            "Maksu vaaditaan ilmoittautumisen vahvistamiseksi - Foo",
            "Sinut on valittu siirrettäväksi tapahtuman <strong>Foo</strong> "
            "jonotuslistalta osallistujaksi. Ole hyvä ja käytä oheista maksulinkkiä "
            "vahvistaaksesi osallistumisesi. Maksulinkki vanhenee %(hours)s tunnin kuluttua."
            % {"hours": settings.WEB_STORE_ORDER_EXPIRATION_HOURS},
        ),
        (
            "sv",
            "Betalning krävs för bekräftelse av registreringen - Foo",
            "Du har blivit utvald att flyttats från väntelistan för evenemanget "
            "<strong>Foo</strong> till att bli en deltagare. Vänligen använd betalningslänken "
            "för att bekräfta ditt deltagande. Betalningslänken går ut efter %(hours)s timmar."
            % {"hours": settings.WEB_STORE_ORDER_EXPIRATION_HOURS},
        ),
    ],
)
@pytest.mark.django_db
def test_send_email_with_payment_link_when_moving_participant_from_waitlist(
    api_client,
    service_language,
    expected_subject,
    expected_text,
):
    language = LanguageFactory(pk=service_language, service_language=True)

    with translation.override(service_language):
        registration = RegistrationFactory(
            event__name="Foo", maximum_attendee_capacity=1
        )

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(registration=registration)

    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    signup = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
    )
    SignUpContactPersonFactory(
        signup=signup, service_language=language, email="test2@test.com"
    )

    signup2 = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.WAITING_LIST
    )
    contact_person2 = SignUpContactPersonFactory(
        signup=signup2,
        first_name="Mickey",
        last_name="Mouse",
        email="test@test.com",
        service_language=language,
    )
    SignUpPriceGroupFactory(
        signup=signup2, registration_price_group=registration_price_group
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 0

    with (
        translation.override(service_language),
        requests_mock.Mocker() as req_mock,
    ):
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            json=DEFAULT_GET_ORDER_DATA,
        )

        assert_delete_signup(
            api_client, signup.id, signup_count=2, contact_person_count=2
        )

        assert req_mock.call_count == 1

    assert SignUpPayment.objects.count() == 1

    signup2.refresh_from_db()
    assert signup2.attendee_status == SignUp.AttendeeStatus.ATTENDING

    assert_payment_link_email_sent(
        contact_person2,
        SignUpPayment.objects.first(),
        expected_mailbox_length=2,
        expected_subject=expected_subject,
        expected_text=expected_text,
    )


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_text",
    [
        (
            "en",
            "Payment required for registration confirmation - Recurring: Foo",
            "You have been selected to be moved from the waiting list of the recurring event "
            "<strong>Foo 1 Feb 2024 - 29 Feb 2024</strong> to a participant. Please use the "
            "payment link to confirm your participation. The payment link expires in "
            "%(hours)s hours." % {"hours": settings.WEB_STORE_ORDER_EXPIRATION_HOURS},
        ),
        (
            "fi",
            "Maksu vaaditaan ilmoittautumisen vahvistamiseksi - Sarja: Foo",
            "Sinut on valittu siirrettäväksi sarjatapahtuman "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong> jonotuslistalta osallistujaksi. Ole hyvä "
            "ja käytä oheista maksulinkkiä vahvistaaksesi osallistumisesi. Maksulinkki vanhenee "
            "%(hours)s tunnin kuluttua."
            % {"hours": settings.WEB_STORE_ORDER_EXPIRATION_HOURS},
        ),
        (
            "sv",
            "Betalning krävs för bekräftelse av registreringen - Serie: Foo",
            "Du har blivit utvald att flyttats från väntelistan för serieevenemanget "
            "<strong>Foo 1.2.2024 - 29.2.2024</strong> till att bli en deltagare. Vänligen använd "
            "betalningslänken för att bekräfta ditt deltagande. Betalningslänken går ut efter "
            "%(hours)s timmar." % {"hours": settings.WEB_STORE_ORDER_EXPIRATION_HOURS},
        ),
    ],
)
@freeze_time("2024-02-01 03:30:00+02:00")
@pytest.mark.django_db
def test_send_email_with_payment_link_when_moving_participant_from_waitlist_for_a_recurring_event(
    api_client,
    service_language,
    expected_subject,
    expected_text,
):
    now = localtime()
    language = LanguageFactory(pk=service_language, service_language=True)

    with translation.override(service_language):
        registration = RegistrationFactory(
            event__start_time=now,
            event__end_time=now + timedelta(days=28),
            event__super_event_type=Event.SuperEventType.RECURRING,
            event__name="Foo",
            maximum_attendee_capacity=1,
        )

    with override_settings(WEB_STORE_INTEGRATION_ENABLED=False):
        RegistrationWebStoreProductMappingFactory(registration=registration)

    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    signup = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
    )
    SignUpContactPersonFactory(
        signup=signup, service_language=language, email="test2@test.com"
    )

    signup2 = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.WAITING_LIST
    )
    contact_person2 = SignUpContactPersonFactory(
        signup=signup2,
        first_name="Mickey",
        last_name="Mouse",
        email="test@test.com",
        service_language=language,
    )
    SignUpPriceGroupFactory(
        signup=signup2, registration_price_group=registration_price_group
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 0

    with (
        translation.override(service_language),
        requests_mock.Mocker() as req_mock,
    ):
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/",
            json=DEFAULT_GET_ORDER_DATA,
        )

        assert_delete_signup(
            api_client, signup.id, signup_count=2, contact_person_count=2
        )

        assert req_mock.call_count == 1

    assert SignUpPayment.objects.count() == 1

    signup2.refresh_from_db()
    assert signup2.attendee_status == SignUp.AttendeeStatus.ATTENDING

    assert_payment_link_email_sent(
        contact_person2,
        SignUpPayment.objects.first(),
        expected_mailbox_length=2,
        expected_subject=expected_subject,
        expected_text=expected_text,
    )


@pytest.mark.parametrize(
    "price,expected_attendee_status,expected_mailbox_count",
    [
        (None, SignUp.AttendeeStatus.WAITING_LIST, 1),
        (Decimal("0"), SignUp.AttendeeStatus.ATTENDING, 2),
    ],
)
@pytest.mark.django_db
def test_email_with_payment_link_not_sent_when_moving_participant_if_price_missing(
    api_client, price, expected_attendee_status, expected_mailbox_count
):
    language = LanguageFactory(pk="en", service_language=True)

    with translation.override(language.pk):
        registration = RegistrationFactory(
            event__name="Foo", maximum_attendee_capacity=1
        )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    signup = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
    )
    contact_person = SignUpContactPersonFactory(
        signup=signup, service_language=language, email="test2@test.com"
    )

    signup2 = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.WAITING_LIST
    )
    contact_person2 = SignUpContactPersonFactory(
        signup=signup2,
        first_name="Mickey",
        last_name="Mouse",
        email="test@test.com",
        service_language=language,
    )

    if price is not None:
        registration_price_group.price = price
        registration_price_group.save()

        SignUpPriceGroupFactory(
            signup=signup2, registration_price_group=registration_price_group
        )

    assert SignUpPayment.objects.count() == 0

    with (
        translation.override(language.pk),
        requests_mock.Mocker() as req_mock,
    ):
        req_mock.post(f"{settings.WEB_STORE_API_BASE_URL}order/")

        assert_delete_signup(
            api_client, signup.id, signup_count=2, contact_person_count=2
        )

        assert req_mock.call_count == 0

    assert SignUpPayment.objects.count() == 0

    signup2.refresh_from_db()
    assert signup2.attendee_status == expected_attendee_status

    assert len(mail.outbox) == expected_mailbox_count
    if expected_mailbox_count == 1:
        assert mail.outbox[0].to[0] == contact_person.email
        assert mail.outbox[0].subject == "Registration cancelled - Foo"
    else:
        assert mail.outbox[0].to[0] == contact_person2.email
        assert mail.outbox[0].subject == "Registration confirmation - Foo"
        assert mail.outbox[1].to[0] == contact_person.email
        assert mail.outbox[1].subject == "Registration cancelled - Foo"


@pytest.mark.parametrize(
    "field,value",
    [
        ("first_name", None),
        ("last_name", None),
        ("email", None),
        ("first_name", ""),
        ("last_name", ""),
        ("email", ""),
        (None, None),
    ],
)
@pytest.mark.django_db
def test_email_with_payment_link_not_sent_when_moving_participant_if_contact_person_is_invalid(
    api_client, field, value
):
    language = LanguageFactory(pk="en", service_language=True)

    with translation.override(language.pk):
        registration = RegistrationFactory(
            event__name="Foo", maximum_attendee_capacity=1
        )

    registration_price_group = RegistrationPriceGroupFactory(registration=registration)

    signup = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.ATTENDING
    )
    contact_person = SignUpContactPersonFactory(
        signup=signup, service_language=language, email="test2@test.com"
    )

    signup2 = SignUpFactory(
        registration=registration, attendee_status=SignUp.AttendeeStatus.WAITING_LIST
    )
    if field:
        SignUpContactPersonFactory(
            signup=signup2,
            first_name="Mickey" if field != "first_name" else value,
            last_name="Mouse" if field != "last_name" else value,
            email="test@test.com" if field != "email" else value,
            service_language=language,
        )
    SignUpPriceGroupFactory(
        signup=signup2, registration_price_group=registration_price_group
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 0

    with (
        translation.override(language.pk),
        requests_mock.Mocker() as req_mock,
    ):
        req_mock.post(f"{settings.WEB_STORE_API_BASE_URL}order/")

        assert_delete_signup(
            api_client,
            signup.id,
            signup_count=2,
            contact_person_count=2 if field else 1,
        )

        assert req_mock.call_count == 0

    assert SignUpPayment.objects.count() == 0

    # Signup 2 status is not changed.
    signup2.refresh_from_db()
    assert signup2.attendee_status == SignUp.AttendeeStatus.WAITING_LIST

    # Email has been sent to signup that was cancelled.
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to[0] == contact_person.email
    assert mail.outbox[0].subject == "Registration cancelled - Foo"


@pytest.mark.django_db
def test_web_store_automatically_fully_refund_paid_signup_payment(
    api_client, price_group
):
    language = LanguageFactory(pk="en", service_language=True)

    signup = price_group.signup
    SignUpContactPersonFactory(
        signup=signup, email="test@test.com", service_language=language
    )
    payment = SignUpPaymentFactory(
        signup=signup,
        external_order_id=DEFAULT_ORDER_ID,
        status=SignUpPayment.PaymentStatus.PAID,
    )

    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentRefund.objects.count() == 0

    with (
        translation.override(language.pk),
        requests_mock.Mocker() as req_mock,
    ):
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            json=DEFAULT_GET_PAYMENT_DATA,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            json=DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        assert req_mock.call_count == 2

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentRefund.objects.count() == 1
    assert (
        SignUpPaymentRefund.objects.filter(
            payment=payment, signup=signup, external_refund_id=DEFAULT_REFUND_ID
        ).count()
        == 1
    )

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_web_store_automatically_fully_refund_paid_signup_payment_errors_in_response(
    api_client, price_group
):
    language = LanguageFactory(pk="en", service_language=True)

    signup = price_group.signup
    SignUpContactPersonFactory(
        signup=signup, email="test@test.com", service_language=language
    )
    payment = SignUpPaymentFactory(
        signup=signup,
        external_order_id=DEFAULT_ORDER_ID,
        status=SignUpPayment.PaymentStatus.PAID,
    )

    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentRefund.objects.count() == 0

    mocked_web_store_json = deepcopy(DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE)
    mocked_web_store_json["errors"] = [
        {
            "code": "refund-error",
            "message": "cannot refund",
        }
    ]

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            json=DEFAULT_GET_PAYMENT_DATA,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            json=mocked_web_store_json,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data[0] == str(mocked_web_store_json["errors"][0])

        assert req_mock.call_count == 2

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentRefund.objects.count() == 0

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_web_store_automatically_cancel_unpaid_created_signup_payment_on_delete(
    api_client, price_group
):
    language = LanguageFactory(pk="en", service_language=True)

    signup = price_group.signup
    SignUpContactPersonFactory(
        signup=signup, email="test@test.com", service_language=language
    )
    payment = SignUpPaymentFactory(
        signup=signup,
        external_order_id=DEFAULT_ORDER_ID,
        status=SignUpPayment.PaymentStatus.CREATED,
    )

    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentCancellation.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}order/admin/{payment.external_order_id}",
            json=DEFAULT_GET_ORDER_DATA,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/{payment.external_order_id}/cancel",
            json=DEFAULT_CANCEL_ORDER_DATA,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        assert req_mock.call_count == 3

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentCancellation.objects.count() == 1
    assert (
        SignUpPaymentCancellation.objects.filter(
            payment=payment,
            signup=signup,
        ).count()
        == 1
    )

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_web_store_partial_refund_when_deleting_signup_from_group_with_payment(
    api_client, price_group
):
    language = LanguageFactory(pk="en", service_language=True)

    price_group.price = _PARTIAL_REFUND_AMOUNT
    price_group.save()

    signup = price_group.signup
    registration = signup.registration

    signup_group = create_signup_group_with_payment(
        signup.registration, service_language=language
    )
    payment = getattr(signup_group, "payment")

    signup.signup_group = signup_group
    signup.save(update_fields=["signup_group"])

    # Second signup price group and signup. Total signup group amount is 10 € (same as the payment).
    create_price_group(
        price_group_kwargs={
            "signup": SignUpFactory(
                signup_group=signup_group, registration=registration
            )
        },
        price=_PARTIAL_REFUND_AMOUNT,
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2
    assert SignUpPaymentRefund.objects.count() == 0

    assert payment.is_fully_refunded is False

    mocked_web_store_json = deepcopy(DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE)
    mocked_web_store_json["refunds"][0]["payment"]["total"] = str(price_group.price)

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            json=DEFAULT_GET_PAYMENT_DATA,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            json=mocked_web_store_json,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        assert req_mock.call_count == 2

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2
    assert SignUpPaymentRefund.objects.count() == 1
    assert (
        SignUpPaymentRefund.objects.filter(
            payment=payment, signup=signup, external_refund_id=DEFAULT_REFUND_ID
        ).count()
        == 1
    )

    payment.refresh_from_db()
    assert payment.is_fully_refunded is False

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_web_store_cannot_cancel_payment_when_deleting_signup_from_group_with_payment(
    api_client, price_group
):
    LanguageFactory(pk="en", service_language=True)

    update_price_group_price(price_group, _PARTIAL_REFUND_AMOUNT)

    signup = price_group.signup

    signup_group = create_signup_group_with_payment(
        signup.registration,
        payment_status=SignUpPayment.PaymentStatus.CREATED,
    )
    payment = getattr(signup_group, "payment")

    signup.signup_group = signup_group
    signup.save(update_fields=["signup_group"])

    # Second signup price group and signup. Total signup group amount is 10 € (same as the payment).
    create_price_group(
        price_group_kwargs={
            "signup": SignUpFactory(
                signup_group=signup_group, registration=signup.registration
            )
        },
        price=_PARTIAL_REFUND_AMOUNT,
    )

    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2
    assert SignUpPaymentCancellation.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}order/admin/{payment.external_order_id}",
            json=DEFAULT_GET_ORDER_DATA,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data[0] == (
            "Cannot cancel payment for a participant that belongs to a group."
        )

        assert req_mock.call_count == 2

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2
    assert SignUpPaymentCancellation.objects.count() == 0

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_web_store_partial_refund_api_exception_when_deleting_signup_from_group_with_payment(
    api_client, price_group
):
    LanguageFactory(pk="en", service_language=True)

    update_price_group_price(price_group, _PARTIAL_REFUND_AMOUNT)

    signup = price_group.signup

    signup_group = create_signup_group_with_payment(signup.registration)
    payment = getattr(signup_group, "payment")

    signup.signup_group = signup_group
    signup.save(update_fields=["signup_group"])

    # Second signup price group and signup. Total signup group amount is 10 € (same as the payment).
    create_price_group(
        price_group_kwargs={
            "signup": SignUpFactory(
                signup_group=signup_group, registration=signup.registration
            )
        },
        price=_PARTIAL_REFUND_AMOUNT,
    )

    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2
    assert SignUpPaymentRefund.objects.count() == 0

    assert payment.is_fully_refunded is False

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            json=DEFAULT_GET_PAYMENT_DATA,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data[0] == (
            f"Payment API experienced an error (code: {status.HTTP_500_INTERNAL_SERVER_ERROR})"
        )

        assert req_mock.call_count == 2

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2
    assert SignUpPaymentRefund.objects.count() == 0

    payment.refresh_from_db()
    assert payment.is_fully_refunded is False

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_web_store_partial_refund_has_errors_when_deleting_signup_from_group_with_payment(
    api_client, price_group
):
    LanguageFactory(pk="en", service_language=True)

    update_price_group_price(price_group, _PARTIAL_REFUND_AMOUNT)

    signup = price_group.signup

    signup_group = create_signup_group_with_payment(signup.registration)
    payment = getattr(signup_group, "payment")

    signup.signup_group = signup_group
    signup.save(update_fields=["signup_group"])

    # Second signup price group and signup. Total signup group amount is 10 € (same as the payment).
    create_price_group(
        price_group_kwargs={
            "signup": SignUpFactory(
                signup_group=signup_group, registration=signup.registration
            )
        },
        price=_PARTIAL_REFUND_AMOUNT,
    )

    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2
    assert SignUpPaymentRefund.objects.count() == 0

    assert payment.is_fully_refunded is False

    mocked_web_store_json = deepcopy(DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE)
    mocked_web_store_json["errors"] = [
        {"code": "validation-error", "message": "Refund validation error"}
    ]

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            json=DEFAULT_GET_PAYMENT_DATA,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            json=mocked_web_store_json,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data[0] == str(mocked_web_store_json["errors"][0])

        assert req_mock.call_count == 2

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2
    assert SignUpPaymentRefund.objects.count() == 0

    payment.refresh_from_db()
    assert payment.is_fully_refunded is False

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_web_store_automatically_fully_refund_paid_signup_payment_api_error(api_client):
    price_group = SignUpPriceGroupFactory()
    signup = price_group.signup
    payment = SignUpPaymentFactory(
        signup=signup,
        external_order_id=DEFAULT_ORDER_ID,
        status=SignUpPayment.PaymentStatus.PAID,
    )

    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentRefund.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            json=DEFAULT_GET_PAYMENT_DATA,
        )

        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data[0] == (
            f"Payment API experienced an error (code: {status.HTTP_500_INTERNAL_SERVER_ERROR})"
        )

        assert req_mock.call_count == 2

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentRefund.objects.count() == 0

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_web_store_refund_refund_id_not_found_exception(api_client, price_group):
    signup = price_group.signup
    payment = SignUpPaymentFactory(
        signup=signup,
        external_order_id=DEFAULT_ORDER_ID,
        status=SignUpPayment.PaymentStatus.PAID,
    )

    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentRefund.objects.count() == 0

    refund_response_without_refund_id = deepcopy(
        DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE
    )
    refund_response_without_refund_id["refunds"][0].pop("refundId")

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            json=DEFAULT_GET_PAYMENT_DATA,
        )

        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/refund/instant",
            json=refund_response_without_refund_id,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data[0] == "Refund ID not found from the response."

        assert req_mock.call_count == 2

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentRefund.objects.count() == 0

    assert len(mail.outbox) == 0


@pytest.mark.parametrize(
    "refund_or_cancel_factory, refund_or_cancel_model",
    [
        (SignUpPaymentRefundFactory, SignUpPaymentRefund),
        (SignUpPaymentCancellationFactory, SignUpPaymentCancellation),
    ],
)
@pytest.mark.django_db
def test_web_store_refund_or_cancellation_already_exists(
    api_client, price_group, refund_or_cancel_factory, refund_or_cancel_model
):
    signup = price_group.signup
    payment = SignUpPaymentFactory(
        signup=signup,
        external_order_id=DEFAULT_ORDER_ID,
        status=SignUpPayment.PaymentStatus.PAID,
    )
    refund_or_cancel_factory(payment=payment, signup=signup)

    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert refund_or_cancel_model.objects.count() == 1

    response = delete_signup(api_client, signup.pk)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == (
        "Refund or cancellation already exists. Please wait for the process to complete."
    )

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert refund_or_cancel_model.objects.count() == 1

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_web_store_automatically_cancel_unpaid_created_signup_payment_api_error(
    api_client,
):
    price_group = SignUpPriceGroupFactory()
    signup = price_group.signup
    payment = SignUpPaymentFactory(
        signup=signup,
        external_order_id=DEFAULT_ORDER_ID,
        status=SignUpPayment.PaymentStatus.CREATED,
    )

    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentCancellation.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}order/admin/{payment.external_order_id}",
            json=DEFAULT_GET_ORDER_DATA,
        )
        req_mock.post(
            f"{settings.WEB_STORE_API_BASE_URL}order/{payment.external_order_id}/cancel",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data[0] == (
            f"Payment API experienced an error (code: {status.HTTP_500_INTERNAL_SERVER_ERROR})"
        )

        assert req_mock.call_count == 3

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentCancellation.objects.count() == 0

    assert len(mail.outbox) == 0


@pytest.mark.parametrize(
    "payment_status_code, order_status_code, expected_calls_count",
    [
        (status.HTTP_500_INTERNAL_SERVER_ERROR, status.HTTP_404_NOT_FOUND, 1),
        (status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR, 2),
    ],
)
@pytest.mark.django_db
def test_web_store_cancel_unpaid_signup_order_or_payment_status_api_error(
    api_client, payment_status_code, order_status_code, expected_calls_count
):
    language = LanguageFactory(pk="en", service_language=True)

    price_group = SignUpPriceGroupFactory()
    signup = price_group.signup
    SignUpContactPersonFactory(
        signup=signup, email="test@test.com", service_language=language
    )
    payment = SignUpPaymentFactory(
        signup=signup,
        external_order_id=DEFAULT_ORDER_ID,
        status=SignUpPayment.PaymentStatus.CREATED,
    )

    user = create_user_by_role("registration_admin", signup.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentCancellation.objects.count() == 0

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            status_code=payment_status_code,
        )

        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}order/admin/{payment.external_order_id}",
            status_code=order_status_code,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data[0] == (
            f"Payment API experienced an error (code: {status.HTTP_500_INTERNAL_SERVER_ERROR})"
        )

        assert req_mock.call_count == expected_calls_count

    assert SignUpPayment.objects.count() == 1
    assert SignUpPriceGroup.objects.count() == 1
    assert SignUpPaymentCancellation.objects.count() == 0

    assert len(mail.outbox) == 0


@pytest.mark.parametrize(
    "payment_status_code, order_status_code, expected_calls_count",
    [
        (status.HTTP_500_INTERNAL_SERVER_ERROR, status.HTTP_404_NOT_FOUND, 1),
        (status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR, 2),
    ],
)
@pytest.mark.django_db
def test_web_store_partial_refund_order_or_payment_status_api_error(
    api_client,
    price_group,
    payment_status_code,
    order_status_code,
    expected_calls_count,
):
    language = LanguageFactory(pk="en", service_language=True)

    signup = price_group.signup
    registration = signup.registration

    signup_group = create_signup_group_with_payment(
        signup.registration, service_language=language
    )
    payment = getattr(signup_group, "payment")

    signup.signup_group = signup_group
    signup.save(update_fields=["signup_group"])

    # Second signup price group and signup. Total signup group amount is 10 € (same as the payment).
    create_price_group(
        price_group_kwargs={
            "signup": SignUpFactory(
                signup_group=signup_group, registration=registration
            )
        },
        price=_PARTIAL_REFUND_AMOUNT,
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2
    assert SignUpPaymentRefund.objects.count() == 0

    assert payment.is_fully_refunded is False

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}payment/admin/{payment.external_order_id}",
            status_code=payment_status_code,
        )
        req_mock.get(
            f"{settings.WEB_STORE_API_BASE_URL}order/admin/{payment.external_order_id}",
            status_code=order_status_code,
        )

        response = delete_signup(api_client, signup.pk)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data[0] == (
            f"Payment API experienced an error (code: {status.HTTP_500_INTERNAL_SERVER_ERROR})"
        )

        assert req_mock.call_count == expected_calls_count

    assert SignUpPayment.objects.count() == 1
    assert SignUp.objects.count() == 2
    assert SignUpPaymentRefund.objects.count() == 0

    payment.refresh_from_db()
    assert payment.is_fully_refunded is False

    assert len(mail.outbox) == 0


@freeze_time("2024-06-26 11:00:00+03:00")
@pytest.mark.parametrize("user_role", ["regular_user", "admin"])
@pytest.mark.django_db
def test_regular_user_or_non_created_admin_cannot_delete_signup_if_event_has_started(
    api_client, organization, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration__event__publisher=organization,
        registration__event__start_time=localtime() - timedelta(hours=1),
        created_by=user,
    )

    response = delete_signup(api_client, signup.pk)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["detail"] == (
        "Only an admin can delete a signup after an event has started."
    )


@freeze_time("2024-06-26 11:00:00+03:00")
@pytest.mark.parametrize(
    "user_role", ["superuser", "registration_admin", "admin", "regular_user"]
)
@pytest.mark.django_db
def test_allowed_user_roles_can_delete_signup_if_event_has_started(
    api_client, organization, user_role
):
    user = create_user_by_role(user_role, organization)
    api_client.force_authenticate(user)

    signup = SignUpFactory(
        registration__event__publisher=organization,
        registration__event__start_time=localtime() - timedelta(hours=1),
        registration__created_by=user if user_role == "admin" else None,
    )

    if user_role == "regular_user":
        user.email = hel_email
        user.save(update_fields=["email"])

        RegistrationUserAccessFactory(
            registration=signup.registration,
            email=user.email,
            is_substitute_user=True,
        )

    assert_delete_signup(api_client, signup.pk, contact_person_count=None)
