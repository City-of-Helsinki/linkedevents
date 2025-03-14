from django.conf import settings


def _get_language_pk_or_default(language, supported_languages):
    if language is not None and language.pk in supported_languages:
        return language.pk
    else:
        return "fi"


def get_signup_create_url(registration, language):
    return (
        f"{settings.LINKED_REGISTRATIONS_UI_URL}/{language}/"
        f"registration/{registration.id}/signup-group/create"
    )


def get_signup_edit_url(
    contact_person, linked_registrations_ui_locale, access_code=None
):
    signup_edit_url = (
        f"{settings.LINKED_REGISTRATIONS_UI_URL}/{linked_registrations_ui_locale}/"
        f"registration/{contact_person.registration.id}/"
    )

    if contact_person.signup_group_id:
        signup_edit_url += f"signup-group/{contact_person.signup_group_id}/edit"
    else:
        signup_edit_url += f"signup/{contact_person.signup_id}/edit"

    if access_code:
        signup_edit_url += f"?access_code={access_code}"

    return signup_edit_url


def get_ui_locales(language):
    linked_events_ui_locale = _get_language_pk_or_default(language, ["fi", "en"])
    linked_registrations_ui_locale = _get_language_pk_or_default(
        language, ["fi", "sv", "en"]
    )

    return [linked_events_ui_locale, linked_registrations_ui_locale]
