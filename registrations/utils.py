from typing import Iterable

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


def code_validity_duration(seats):
    return settings.SEAT_RESERVATION_DURATION + seats


def get_language_pk_or_default(language, supported_languages):
    if language is not None and language.pk in supported_languages:
        return language.pk
    else:
        return "fi"


def get_ui_locales(language):
    linked_events_ui_locale = get_language_pk_or_default(language, ["fi", "en"])
    linked_registrations_ui_locale = get_language_pk_or_default(
        language, ["fi", "sv", "en"]
    )

    return [linked_events_ui_locale, linked_registrations_ui_locale]


def get_signup_edit_url(contact_person, linked_registrations_ui_locale):
    signup_edit_url = (
        f"{settings.LINKED_REGISTRATIONS_UI_URL}/{linked_registrations_ui_locale}"
        f"/registration/{contact_person.registration.id}/"
    )

    if contact_person.signup_group_id:
        signup_edit_url += f"signup-group/{contact_person.signup_group_id}/edit"
    else:
        signup_edit_url += f"signup/{contact_person.signup_id}/edit"

    return signup_edit_url


def send_mass_html_mail(
    datatuple,
    fail_silently=False,
    auth_user=None,
    auth_password=None,
    connection=None,
):
    """
    django.core.mail.send_mass_mail doesn't support sending html mails,

    This method duplicates send_mass_mail except requires html_message for each message
    and adds html alternative to each mail
    """
    connection = connection or get_connection(
        username=auth_user,
        password=auth_password,
        fail_silently=fail_silently,
    )
    messages = []
    for subject, message, html_message, from_email, recipient_list in datatuple:
        mail = EmailMultiAlternatives(
            subject, message, from_email, recipient_list, connection=connection
        )
        mail.attach_alternative(html_message, "text/html")
        messages.append(mail)

    return connection.send_messages(messages)


def get_email_noreply_address():
    return (
        settings.DEFAULT_FROM_EMAIL or "noreply@%s" % Site.objects.get_current().domain
    )


def validate_mandatory_fields(data, mandatory_fields: Iterable[str], partial: bool):
    falsy_values = ("", None)
    errors = {}

    # Validate mandatory fields
    for field in mandatory_fields:
        # Don't validate field if request method is PATCH and field is missing from the payload
        if partial and field not in data.keys():
            continue
        elif data.get(field) in falsy_values:
            errors[field] = _("This field must be specified.")

    return errors
