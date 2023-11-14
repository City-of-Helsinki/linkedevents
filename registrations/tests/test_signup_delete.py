import pytest
from django.core import mail
from django.utils import translation
from rest_framework import status

from audit_log.models import AuditLogEntry
from events.models import Event, Language
from events.tests.utils import versioned_reverse as reverse
from helevents.tests.factories import UserFactory
from registrations.models import SignUp
from registrations.tests.factories import (
    RegistrationUserAccessFactory,
    SeatReservationCodeFactory,
    SignUpFactory,
    SignUpGroupFactory,
)
from registrations.tests.test_signup_post import assert_create_signups

# === util methods ===


def delete_signup(api_client, signup_pk, query_string=None):
    signup_url = reverse(
        "signup-detail",
        kwargs={"pk": signup_pk},
    )
    if query_string:
        signup_url = "%s?%s" % (signup_url, query_string)

    return api_client.delete(signup_url)


def assert_delete_signup(api_client, signup_pk, query_string=None):
    response = delete_signup(api_client, signup_pk, query_string)
    assert response.status_code == status.HTTP_204_NO_CONTENT


# === tests ===


@pytest.mark.django_db
def test_admin_cannot_delete_signup(signup, user_api_client):
    response = delete_signup(user_api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_registration_admin_can_delete_signup(signup, user, user_api_client):
    default_organization = user.get_default_organization()
    default_organization.admin_users.remove(user)
    default_organization.registration_admin_users.add(user)

    assert_delete_signup(user_api_client, signup.id)


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_heading,expected_text",
    [
        (
            "en",
            "Registration cancelled",
            "Username, registration to the event Foo has been cancelled.",
            "You have successfully cancelled your registration to the event <strong>Foo</strong>.",
        ),
        (
            "fi",
            "Ilmoittautuminen peruttu",
            "Username, ilmoittautuminen tapahtumaan Foo on peruttu.",
            "Olet onnistuneesti peruuttanut ilmoittautumisesi tapahtumaan <strong>Foo</strong>.",
        ),
        (
            "sv",
            "Registreringen avbruten",
            "Username, anmälan till evenemanget Foo har ställts in.",
            "Du har avbrutit din registrering till evenemanget <strong>Foo</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_email_sent_on_successful_signup_deletion(
    expected_heading,
    expected_subject,
    expected_text,
    languages,
    registration,
    service_language,
    signup,
    user_api_client,
    user,
):

    user.get_default_organization().registration_admin_users.add(user)

    signup.first_name = "Username"
    signup.service_language = Language.objects.get(pk=service_language)
    signup.save()

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
    languages,
    registration,
    signup,
    user_api_client,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    signup.first_name = "Username"
    signup.service_language = Language.objects.get(pk="en")
    signup.save()

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()

    assert_delete_signup(user_api_client, signup.id)
    #  assert that the email was sent
    assert len(mail.outbox) == 1
    assert expected_heading in str(mail.outbox[0].alternatives[0])
    assert expected_text in str(mail.outbox[0].alternatives[0])


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
def test_regular_not_created_user_cannot_delete_signup(signup, user, user_api_client):
    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    response = delete_signup(user_api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


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

    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_created_not_authenticated_user_cannot_delete_signup(
    user_api_client, signup, user
):
    signup.created_by = user
    signup.save(update_fields=["created_by"])

    user_api_client.logout()

    user.get_default_organization().regular_users.add(user)
    user.get_default_organization().admin_users.remove(user)

    response = delete_signup(user_api_client, signup.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


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

    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_from_wrong_data_source_cannot_delete_signup(
    api_client, organization, other_data_source, signup
):
    other_data_source.owner = organization
    other_data_source.save()
    api_client.credentials(apikey=other_data_source.api_key)

    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_unknown_api_key_cannot_delete_signup(api_client, signup):
    api_client.credentials(apikey="unknown")

    response = delete_signup(api_client, signup.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


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
        "email": "test@test.com",
        "attendee_status": attendee_status,
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
        "email": "test1@test.com",
        "attendee_status": SignUp.AttendeeStatus.WAITING_LIST,
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
        "email": "test2@test.com",
        "attendee_status": SignUp.AttendeeStatus.WAITING_LIST,
    }
    signups_data3 = {
        "registration": registration.id,
        "reservation_code": reservation3.code,
        "signups": [signup_data3],
    }
    assert_create_signups(api_client, signups_data3)

    assert (
        SignUp.objects.get(email=signup_data["email"]).attendee_status
        == attendee_status
    )
    assert (
        SignUp.objects.get(email=signup_data2["email"]).attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )
    assert (
        SignUp.objects.get(email=signup_data3["email"]).attendee_status
        == SignUp.AttendeeStatus.WAITING_LIST
    )

    assert_delete_signup(api_client, signup_id)
    assert (
        SignUp.objects.get(email=signup_data2["email"]).attendee_status
        == attendee_status
    )
    assert (
        SignUp.objects.get(email=signup_data3["email"]).attendee_status
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
    languages,
    registration,
    service_language,
    signup,
    signup2,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()
        registration.maximum_attendee_capacity = 1
        registration.save()

        signup.attendee_status = SignUp.AttendeeStatus.ATTENDING
        signup.save()

        signup2.attendee_status = SignUp.AttendeeStatus.WAITING_LIST
        signup2.service_language = Language.objects.get(pk=service_language)
        signup2.save()

        signup_id = signup.id
        assert_delete_signup(user_api_client, signup_id)

        # Signup 2 status should be changed
        assert (
            SignUp.objects.get(pk=signup2.pk).attendee_status
            == SignUp.AttendeeStatus.ATTENDING
        )
        # Send email to signup who is transferred as participant
        assert mail.outbox[1].subject.startswith(expected_subject)
        assert expected_text in str(mail.outbox[1].alternatives[0])


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
    languages,
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
    registration.save()

    signup.attendee_status = SignUp.AttendeeStatus.ATTENDING
    signup.save()

    signup2.attendee_status = SignUp.AttendeeStatus.WAITING_LIST
    signup2.service_language = Language.objects.get(pk="en")
    signup2.save()

    signup_id = signup.id
    assert_delete_signup(user_api_client, signup_id)

    # Signup 2 status should be changed
    assert (
        SignUp.objects.get(pk=signup2.pk).attendee_status
        == SignUp.AttendeeStatus.ATTENDING
    )
    # Send email to signup who is transferred as participant
    assert mail.outbox[1].subject.startswith(expected_subject)
    assert expected_text in str(mail.outbox[1].alternatives[0])


@pytest.mark.parametrize("responsible_for_group", [True, False])
@pytest.mark.django_db
def test_delete_signup_from_group(api_client, registration, responsible_for_group):
    user = UserFactory()
    user.registration_admin_organizations.add(registration.publisher)
    api_client.force_authenticate(user)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(registration=registration, signup_group=signup_group)
    responsible_signup = SignUpFactory(
        registration=registration,
        signup_group=signup_group,
        responsible_for_group=responsible_for_group,
    )

    assert SignUp.objects.count() == 2

    response = delete_signup(api_client, responsible_signup.pk)

    if responsible_for_group:
        # Only responsible signup cannot be deleted
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert SignUp.objects.count() == 2
    else:
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
