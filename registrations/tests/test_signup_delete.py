from datetime import timedelta
from unittest.mock import patch, PropertyMock

import pytest
from django.core import mail
from django.utils import translation
from django.utils.timezone import localtime
from freezegun import freeze_time
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event
from events.tests.factories import LanguageFactory
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp, SignUpContactPerson, SignUpPriceGroup
from registrations.tests.factories import (
    RegistrationFactory,
    RegistrationUserAccessFactory,
    SeatReservationCodeFactory,
    SignUpContactPersonFactory,
    SignUpFactory,
    SignUpGroupFactory,
    SignUpPriceGroupFactory,
)
from registrations.tests.test_registration_post import hel_email
from registrations.tests.test_signup_post import assert_create_signups
from registrations.tests.utils import create_user_by_role

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
    api_client, signup_pk, query_string=None, signup_count=1, contact_person_count=1
):
    assert SignUp.objects.count() == signup_count
    assert SignUpContactPerson.objects.count() == contact_person_count

    response = delete_signup(api_client, signup_pk, query_string)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert SignUp.objects.count() == (signup_count - 1 if signup_count else 0)

    if contact_person_count:
        assert SignUpContactPerson.objects.count() == contact_person_count - 1
    else:
        assert SignUpContactPerson.objects.count() == 0


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


@pytest.mark.django_db
def test_registration_non_created_admin_cannot_delete_signup(
    registration, signup, user2, user_api_client
):
    registration.created_by = user2
    registration.save(update_fields=["created_by"])

    assert_delete_signup_failed(user_api_client, signup.id)


@pytest.mark.django_db
def test_registration_created_admin_can_delete_signup(
    registration, signup, user, user_api_client
):
    registration.created_by = user
    registration.save(update_fields=["created_by"])

    assert_delete_signup(user_api_client, signup.id)


@pytest.mark.django_db
def test_registration_admin_can_delete_signup(signup, user, user_api_client):
    default_organization = user.get_default_organization()
    default_organization.admin_users.remove(user)
    default_organization.registration_admin_users.add(user)

    assert_delete_signup(user_api_client, signup.id)


@pytest.mark.django_db
def test_contact_person_can_delete_signup_when_strongly_identified(
    api_client, registration
):
    user = UserFactory()
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
    user = UserFactory()
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
    user_api_client,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    signup.contact_person.first_name = username
    signup.contact_person.service_language = LanguageFactory(
        pk=service_language, service_language=True
    )
    signup.contact_person.save(update_fields=["first_name", "service_language"])

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()

        assert_delete_signup(user_api_client, signup.id)
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

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(
        signup=signup, first_name=username, service_language=lang, email="test@test.com"
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

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
    user_api_client,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    signup.contact_person.first_name = "Username"
    signup.contact_person.service_language = LanguageFactory(
        pk="en", service_language=True
    )
    signup.contact_person.save(update_fields=["first_name", "service_language"])

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()

    assert_delete_signup(user_api_client, signup.id)
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

    signup = SignUpFactory(registration=registration)
    SignUpContactPersonFactory(
        signup=signup,
        first_name="Username",
        service_language=lang,
        email="test@test.com",
    )

    user = create_user_by_role("registration_admin", registration.publisher)
    api_client.force_authenticate(user)

    assert_delete_signup(api_client, signup.id)

    #  assert that the email was sent
    message_html_string = str(mail.outbox[0].alternatives[0])
    assert len(mail.outbox) == 1
    assert expected_heading in message_html_string
    assert expected_text in message_html_string


@pytest.mark.django_db
def test_cannot_delete_already_deleted_signup(signup, user_api_client, user):
    user.get_default_organization().registration_admin_users.add(user)

    assert_delete_signup(user_api_client, signup.id)
    response = delete_signup(user_api_client, signup.id)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_registration_user_access_cannot_delete_signup(
    registration, signup, user, user_api_client
):
    user.get_default_organization().admin_users.remove(user)
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    response = delete_signup(user_api_client, signup.id)
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
def test_non_created_financial_admin_cannot_delete_signup(signup, api_client):
    user = UserFactory()
    user.financial_admin_organizations.add(signup.publisher)
    api_client.force_authenticate(user)

    assert_delete_signup_failed(api_client, signup.id)


@pytest.mark.django_db
def test_created_financial_admin_can_delete_signup(signup, api_client):
    user = UserFactory()
    user.financial_admin_organizations.add(signup.publisher)
    api_client.force_authenticate(user)

    signup.created_by = user
    signup.save(update_fields=["created_by"])

    assert_delete_signup(api_client, signup.id)


@pytest.mark.django_db
def test_regular_not_created_user_cannot_delete_signup(signup, user, user_api_client):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    assert_delete_signup_failed(user_api_client, signup.id)


@pytest.mark.django_db
def test_created_user_without_organization_can_delete_signup(
    user_api_client, signup, user
):
    signup.created_by = user
    signup.save(update_fields=["created_by"])

    user.get_default_organization().admin_users.remove(user)

    assert_delete_signup(user_api_client, signup.id)


@pytest.mark.django_db
def test_not_created_user_without_organization_cannot_delete_signup(api_client, signup):
    user = UserFactory()
    api_client.force_authenticate(user)

    assert_delete_signup_failed(api_client, signup.id)


@pytest.mark.django_db
def test_created_not_authenticated_user_cannot_delete_signup(
    user_api_client, signup, user
):
    signup.created_by = user
    signup.save(update_fields=["created_by"])

    user_api_client.logout()

    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    assert_delete_signup_failed(
        user_api_client, signup.id, status_code=status.HTTP_401_UNAUTHORIZED
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


@pytest.mark.django_db
def test_unknown_api_key_cannot_delete_signup(api_client, signup):
    api_client.credentials(apikey="unknown")

    assert_delete_signup_failed(
        api_client, signup.id, status_code=status.HTTP_401_UNAUTHORIZED
    )


@pytest.mark.parametrize("user_editable_resources", [False, True])
@pytest.mark.django_db
def test_registration_admin_can_delete_signup_regardless_of_non_user_editable_resources(
    data_source, organization, signup, user, user_api_client, user_editable_resources
):
    user.get_default_organization().registration_admin_users.add(user)

    data_source.owner = organization
    data_source.user_editable_resources = user_editable_resources
    data_source.save(update_fields=["owner", "user_editable_resources"])

    assert_delete_signup(user_api_client, signup.id)


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
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
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
    user_api_client,
    expected_subject,
    expected_text,
    registration,
    service_language,
    signup,
    signup2,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

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
            user_api_client, signup.id, signup_count=2, contact_person_count=2
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
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
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
    user_api_client,
    event_type,
    expected_subject,
    expected_text,
    registration,
    signup,
    signup2,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

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

    assert_delete_signup(
        user_api_client, signup.id, signup_count=2, contact_person_count=2
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
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
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
