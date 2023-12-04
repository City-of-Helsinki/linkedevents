from typing import Optional, TYPE_CHECKING

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.base import BaseEmailBackend

if TYPE_CHECKING:
    from events.models import Language
    from registrations.models import SignUpContactPerson


def code_validity_duration(seats: int) -> int:
    return settings.SEAT_RESERVATION_DURATION + seats


def get_language_pk_or_default(
    language: "Language", supported_languages: list[str]
) -> str:
    if language is not None and language.pk in supported_languages:
        return language.pk
    else:
        return "fi"


def get_ui_locales(language: "Language") -> list[str]:
    linked_events_ui_locale = get_language_pk_or_default(language, ["fi", "en"])
    linked_registrations_ui_locale = get_language_pk_or_default(
        language, ["fi", "sv", "en"]
    )

    return [linked_events_ui_locale, linked_registrations_ui_locale]


def get_signup_edit_url(
    contact_person: "SignUpContactPerson", linked_registrations_ui_locale: str
) -> str:
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
    datatuple: tuple,
    fail_silently: bool = False,
    auth_user: Optional[str] = None,
    auth_password: Optional[str] = None,
    connection: Optional[BaseEmailBackend] = None,
) -> int:
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


def get_email_noreply_address() -> str:
    return (
        settings.DEFAULT_FROM_EMAIL or "noreply@%s" % Site.objects.get_current().domain
    )
