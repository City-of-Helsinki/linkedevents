import pytest
from django.core import mail
from django.utils import translation
from rest_framework import status

from events.models import Event
from events.tests.factories import LanguageFactory
from events.tests.utils import versioned_reverse as reverse
from registrations.models import SignUp, SignUpGroup
from registrations.tests.factories import (
    RegistrationUserAccessFactory,
    SignUpFactory,
    SignUpGroupFactory,
)

# === util methods ===


def delete_signup_group(api_client, signup_group_pk, query_string=None):
    signup_group_url = reverse(
        "signupgroup-detail",
        kwargs={"pk": signup_group_pk},
    )
    if query_string:
        signup_group_url = "%s?%s" % (signup_group_url, query_string)

    return api_client.delete(signup_group_url)


def assert_delete_signup_group(api_client, signup_group_pk, query_string=None):
    response = delete_signup_group(api_client, signup_group_pk, query_string)
    assert response.status_code == status.HTTP_204_NO_CONTENT


# === tests ===


@pytest.mark.django_db
def test_registration_admin_can_delete_signup_group(
    user_api_client, registration, user
):
    default_organization = user.get_default_organization()
    default_organization.admin_users.remove(user)
    default_organization.registration_admin_users.add(user)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)

    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    assert_delete_signup_group(user_api_client, signup_group.id)

    assert SignUpGroup.objects.count() == 0
    assert SignUp.objects.count() == 0


@pytest.mark.django_db
def test_admin_cannot_delete_signup_group(user_api_client, registration, user):
    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)

    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    response = delete_signup_group(user_api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2


@pytest.mark.django_db
def test_regular_user_cannot_delete_signup_group(user_api_client, registration, user):
    default_organization = user.get_default_organization()
    default_organization.admin_users.remove(user)
    default_organization.regular_users.add(user)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)

    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    response = delete_signup_group(user_api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2


@pytest.mark.django_db
def test_registration_user_access_cannot_delete_signup_group(
    user_api_client, registration, user
):
    user.get_default_organization().admin_users.remove(user)
    RegistrationUserAccessFactory(registration=registration, email=user.email)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)
    SignUpFactory(signup_group=signup_group, registration=registration)

    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2

    response = delete_signup_group(user_api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert SignUpGroup.objects.count() == 1
    assert SignUp.objects.count() == 2


@pytest.mark.parametrize(
    "service_language,expected_subject,expected_heading,expected_text",
    [
        (
            "en",
            "Registration cancelled",
            "Registration to the event Foo has been cancelled.",
            "You have successfully cancelled your registration to the event <strong>Foo</strong>.",
        ),
        (
            "fi",
            "Ilmoittautuminen peruttu",
            "Ilmoittautuminen tapahtumaan Foo on peruttu.",
            "Olet onnistuneesti peruuttanut ilmoittautumisesi tapahtumaan <strong>Foo</strong>.",
        ),
        (
            "sv",
            "Registreringen avbruten",
            "Anmälan till evenemanget Foo har ställts in.",
            "Du har avbrutit din registrering till evenemanget <strong>Foo</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_email_sent_on_successful_signup_group_deletion(
    expected_heading,
    expected_subject,
    expected_text,
    registration,
    service_language,
    user_api_client,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    service_lang = LanguageFactory(id=service_language, service_language=True)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        service_language=service_lang,
        email="test@test.com",
    )

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()

        assert_delete_signup_group(user_api_client, signup_group.id)

        #  assert that the email was sent
        assert mail.outbox[0].subject.startswith(expected_subject)
        assert expected_heading in str(mail.outbox[0].alternatives[0])
        assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.parametrize(
    "event_type,expected_heading,expected_text",
    [
        (
            Event.TypeId.GENERAL,
            "Registration to the event Foo has been cancelled.",
            "You have successfully cancelled your registration to the event <strong>Foo</strong>.",
        ),
        (
            Event.TypeId.COURSE,
            "Registration to the course Foo has been cancelled.",
            "You have successfully cancelled your registration to the course <strong>Foo</strong>.",
        ),
        (
            Event.TypeId.VOLUNTEERING,
            "Registration to the volunteering Foo has been cancelled.",
            "You have successfully cancelled your registration to the volunteering <strong>Foo</strong>.",
        ),
    ],
)
@pytest.mark.django_db
def test_signup_group_cancellation_confirmation_template_has_correct_text_per_event_type(
    event_type,
    expected_heading,
    expected_text,
    registration,
    user_api_client,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    service_lang = LanguageFactory(pk="en", service_language=True)

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        service_language=service_lang,
        email="test@test.com",
    )
    SignUpFactory(
        signup_group=signup_group,
        registration=registration,
        service_language=service_lang,
        email="test2@test.com",
    )

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()

    assert_delete_signup_group(user_api_client, signup_group.id)

    #  assert that the emails were sent to both sign-up emails
    assert len(mail.outbox) == 2
    assert expected_heading in str(mail.outbox[0].alternatives[0])
    assert expected_text in str(mail.outbox[0].alternatives[0])


@pytest.mark.django_db
def test_cannot_delete_already_deleted_signup_group(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_group = SignUpGroupFactory(registration=registration)

    assert_delete_signup_group(user_api_client, signup_group.id)
    response = delete_signup_group(user_api_client, signup_group.id)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_created_authenticated_user_can_delete_signup_group(
    user_api_client, user, registration
):
    signup_group = SignUpGroupFactory(registration=registration, created_by=user)

    default_org = user.get_default_organization()
    default_org.regular_users.add(user)
    default_org.admin_users.remove(user)

    assert_delete_signup_group(user_api_client, signup_group.id)


@pytest.mark.django_db
def test_created_not_authenticated_user_cannot_delete_signup_group(
    user_api_client, user, organization
):
    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization, created_by=user
    )

    user_api_client.logout()

    default_org = user.get_default_organization()
    default_org.regular_users.add(user)
    default_org.admin_users.remove(user)

    response = delete_signup_group(user_api_client, signup_group.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_api_key_with_organization_and_user_editable_registrations_can_delete_signup_group(
    api_client,
    data_source,
    organization,
):
    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization,
        registration__event__data_source=data_source,
    )

    data_source.owner = organization
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=data_source.api_key)

    assert_delete_signup_group(api_client, signup_group.id)


@pytest.mark.django_db
def test_api_key_of_other_organization_and_user_editable_registrations_cannot_delete_signup_group(
    api_client, data_source, organization2, organization
):
    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization,
        registration__event__data_source=organization.data_source,
    )

    data_source.owner = organization2
    data_source.user_editable_registrations = True
    data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=data_source.api_key)

    response = delete_signup_group(api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_api_key_from_wrong_data_source_cannot_delete_signup_group(
    api_client, organization, other_data_source
):
    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization,
        registration__event__data_source=organization.data_source,
    )

    other_data_source.owner = organization
    other_data_source.user_editable_registrations = True
    other_data_source.save(update_fields=["owner", "user_editable_registrations"])
    api_client.credentials(apikey=other_data_source.api_key)

    response = delete_signup_group(api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_unknown_api_key_cannot_delete_signup_group(api_client, organization):
    signup_group = SignUpGroupFactory(registration__event__publisher=organization)

    api_client.credentials(apikey="unknown")

    response = delete_signup_group(api_client, signup_group.id)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_user_editable_resources_can_delete_signup_group(
    data_source, organization, user, user_api_client
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization,
        registration__event__data_source=data_source,
    )

    data_source.owner = organization
    data_source.user_editable_resources = True
    data_source.save(update_fields=["owner", "user_editable_resources"])

    assert_delete_signup_group(user_api_client, signup_group.id)


@pytest.mark.django_db
def test_non_user_editable_resources_cannot_delete_signup_group(
    data_source, organization, user, user_api_client
):
    user.get_default_organization().registration_admin_users.add(user)

    signup_group = SignUpGroupFactory(
        registration__event__publisher=organization,
        registration__event__data_source=data_source,
    )

    data_source.owner = organization
    data_source.user_editable_resources = False
    data_source.save(update_fields=["owner", "user_editable_resources"])

    response = delete_signup_group(user_api_client, signup_group.id)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_signup_group_deletion_leads_to_changing_status_of_first_waitlisted_user(
    user_api_client, registration, user
):
    user.get_default_organization().registration_admin_users.add(user)

    registration.maximum_attendee_capacity = 1
    registration.save(update_fields=["maximum_attendee_capacity"])

    signup_group0 = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group0,
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
    )

    signup_group1 = SignUpGroupFactory(registration=registration)
    signup1 = SignUpFactory(
        signup_group=signup_group1,
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
    )

    signup_group2 = SignUpGroupFactory(registration=registration)
    signup2 = SignUpFactory(
        signup_group=signup_group2,
        registration=registration,
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
    )

    assert signup1.attendee_status == SignUp.AttendeeStatus.WAITING_LIST
    assert signup2.attendee_status == SignUp.AttendeeStatus.WAITING_LIST

    assert_delete_signup_group(user_api_client, signup_group0.pk)

    signup1.refresh_from_db()
    signup2.refresh_from_db()
    assert signup1.attendee_status == SignUp.AttendeeStatus.ATTENDING
    assert signup2.attendee_status == SignUp.AttendeeStatus.WAITING_LIST


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
def test_signup_group_send_email_when_moving_participant_from_waitlist(
    user_api_client,
    expected_subject,
    expected_text,
    registration,
    service_language,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    service_lang = LanguageFactory(pk=service_language, service_language=True)

    with translation.override(service_language):
        registration.event.type_id = Event.TypeId.GENERAL
        registration.event.name = "Foo"
        registration.event.save()

        registration.maximum_attendee_capacity = 1
        registration.save(update_fields=["maximum_attendee_capacity"])

        signup_group = SignUpGroupFactory(registration=registration)
        SignUpFactory(
            signup_group=signup_group,
            attendee_status=SignUp.AttendeeStatus.ATTENDING,
            registration=registration,
            email="test@test.com",
        )
        signup1 = SignUpFactory(
            attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
            registration=registration,
            service_language=service_lang,
            email="test@test2.com",
        )

        assert signup1.attendee_status == SignUp.AttendeeStatus.WAITING_LIST

        assert_delete_signup_group(user_api_client, signup_group.pk)

        # signup1's status should be changed
        signup1.refresh_from_db()
        assert signup1.attendee_status == SignUp.AttendeeStatus.ATTENDING
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
def test_signup_group_transferred_as_participant_template_has_correct_text_per_event_type(
    user_api_client,
    event_type,
    expected_subject,
    expected_text,
    registration,
    user,
):
    user.get_default_organization().registration_admin_users.add(user)

    service_lang = LanguageFactory(pk="en", service_language=True)

    registration.event.type_id = event_type
    registration.event.name = "Foo"
    registration.event.save()

    registration.maximum_attendee_capacity = 1
    registration.save(update_fields=["maximum_attendee_capacity"])

    signup_group = SignUpGroupFactory(registration=registration)
    SignUpFactory(
        signup_group=signup_group,
        attendee_status=SignUp.AttendeeStatus.ATTENDING,
        registration=registration,
        email="test@test0.com",
    )
    signup1 = SignUpFactory(
        attendee_status=SignUp.AttendeeStatus.WAITING_LIST,
        registration=registration,
        service_language=service_lang,
        email="test@test.com",
    )

    assert signup1.attendee_status == SignUp.AttendeeStatus.WAITING_LIST

    assert_delete_signup_group(user_api_client, signup_group.pk)

    # signup1's status should be changed
    signup1.refresh_from_db()
    assert signup1.attendee_status == SignUp.AttendeeStatus.ATTENDING
    # Send email to signup who is transferred as participant
    assert mail.outbox[1].subject.startswith(expected_subject)
    assert expected_text in str(mail.outbox[1].alternatives[0])