from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from events.models import Event
from registrations.utils import get_signup_edit_url, get_ui_locales


class SignUpNotificationType:
    CANCELLATION = "cancellation"
    CONFIRMATION = "confirmation"
    CONFIRMATION_TO_WAITING_LIST = "confirmation_to_waiting_list"
    TRANSFERRED_AS_PARTICIPANT = "transferred_as_participant"


signup_email_texts = {
    SignUpNotificationType.CANCELLATION: {
        "heading": _("Registration cancelled"),
        "secondary_heading": {
            Event.TypeId.GENERAL: _(
                "%(username)s, registration to the event %(event_name)s has been cancelled."
            ),
            Event.TypeId.COURSE: _(
                "%(username)s, registration to the course %(event_name)s has been cancelled."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "%(username)s, registration to the volunteering %(event_name)s has been cancelled."
            ),
        },
        "text": {
            Event.TypeId.GENERAL: _(
                "You have successfully cancelled your registration to the event <strong>%(event_name)s</strong>."
            ),
            Event.TypeId.COURSE: _(
                "You have successfully cancelled your registration to the course <strong>%(event_name)s</strong>."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You have successfully cancelled your registration to the volunteering <strong>%(event_name)s</strong>."
            ),
        },
    },
    SignUpNotificationType.CONFIRMATION: {
        "heading": _("Welcome %(username)s"),
        "secondary_heading": {
            Event.TypeId.GENERAL: _(
                "Registration to the event %(event_name)s has been saved."
            ),
            Event.TypeId.COURSE: _(
                "Registration to the course %(event_name)s has been saved."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Registration to the volunteering %(event_name)s has been saved."
            ),
        },
        "text": {
            Event.TypeId.GENERAL: _(
                "Congratulations! Your registration has been confirmed for the event <strong>%(event_name)s</strong>."
            ),
            Event.TypeId.COURSE: _(
                "Congratulations! Your registration has been confirmed for the course <strong>%(event_name)s</strong>."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Congratulations! Your registration has been confirmed for the volunteering <strong>%(event_name)s</strong>."  # noqa E501
            ),
        },
        "group": {
            "heading": _("Welcome"),
            "secondary_heading": {
                Event.TypeId.GENERAL: _(
                    "Group registration to the event %(event_name)s has been saved."
                ),
                Event.TypeId.COURSE: _(
                    "Group registration to the course %(event_name)s has been saved."
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "Group registration to the volunteering %(event_name)s has been saved."
                ),
            },
        },
    },
    SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST: {
        "heading": _("Thank you for signing up for the waiting list"),
        "text": {
            Event.TypeId.GENERAL: _(
                "You have successfully registered for the event <strong>%(event_name)s</strong> waiting list."
            ),
            Event.TypeId.COURSE: _(
                "You have successfully registered for the course <strong>%(event_name)s</strong> waiting list."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You have successfully registered for the volunteering <strong>%(event_name)s</strong> waiting list."
            ),
        },
        "secondary_text": {
            Event.TypeId.GENERAL: _(
                "You will be automatically transferred as an event participant if a seat becomes available."
            ),
            Event.TypeId.COURSE: _(
                "You will be automatically transferred as a course participant if a seat becomes available."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You will be automatically transferred as a volunteering participant if a seat becomes available."
            ),
        },
        "group": {
            "text": {
                Event.TypeId.GENERAL: _(
                    "The registration for the event <strong>%(event_name)s</strong> waiting list was successful."
                ),
                Event.TypeId.COURSE: _(
                    "The registration for the course <strong>%(event_name)s</strong> waiting list was successful."
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "The registration for the volunteering <strong>%(event_name)s</strong> waiting list was successful."
                ),
            },
            "secondary_text": {
                Event.TypeId.GENERAL: _(
                    "You will be automatically transferred from the waiting list to become a participant in the event if a place becomes available."  # noqa E501
                ),
                Event.TypeId.COURSE: _(
                    "You will be automatically transferred from the waiting list to become a participant in the course if a place becomes available."  # noqa E501
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "You will be automatically transferred from the waiting list to become a participant in the volunteering if a place becomes available."  # noqa E501
                ),
            },
        },
    },
    SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT: {
        "heading": _("Welcome %(username)s"),
        "text": {
            Event.TypeId.GENERAL: _(
                "You have been moved from the waiting list of the event <strong>%(event_name)s</strong> to a participant."  # noqa E501
            ),
            Event.TypeId.COURSE: _(
                "You have been moved from the waiting list of the course <strong>%(event_name)s</strong> to a participant."  # noqa E501
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You have been moved from the waiting list of the volunteering <strong>%(event_name)s</strong> to a participant."  # noqa E501
            ),
        },
    },
}


def get_signup_notification_texts(signup, notification_type: SignUpNotificationType):
    with (translation.override(signup.get_service_language_pk())):
        confirmation_message = signup.registration.confirmation_message
        event_name = signup.registration.event.name

    event_type_id = signup.registration.event.type_id
    username = signup.first_name
    text_options = signup_email_texts[notification_type]
    texts = {
        "heading": text_options["heading"] % {"username": username},
        "text": text_options["text"][event_type_id] % {"event_name": event_name},
    }

    if notification_type == SignUpNotificationType.CANCELLATION:
        texts["secondary_heading"] = text_options["secondary_heading"][
            event_type_id
        ] % {
            "event_name": event_name,
            "username": username,
        }
    elif notification_type == SignUpNotificationType.CONFIRMATION:
        if signup.signup_group_id:
            # Override default confirmation message heading
            texts["heading"] = text_options["group"]["heading"]
            texts["secondary_heading"] = text_options["group"]["secondary_heading"][
                event_type_id
            ] % {"event_name": event_name}
        else:
            texts["secondary_heading"] = text_options["secondary_heading"][
                event_type_id
            ] % {"event_name": event_name}
    elif notification_type == SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST:
        if signup.signup_group_id:
            # Override default confirmation message heading
            texts["text"] = text_options["group"]["text"][event_type_id] % {
                "event_name": event_name
            }
            texts["secondary_text"] = text_options["group"]["secondary_text"][
                event_type_id
            ]
        else:
            texts["secondary_text"] = text_options["secondary_text"][event_type_id]

    if (
        notification_type == SignUpNotificationType.CONFIRMATION
        or notification_type == SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT
    ) and confirmation_message:
        texts["confirmation_message"] = confirmation_message

    return texts


def get_signup_notification_subject(signup, notification_type):
    linked_registrations_ui_locale = get_ui_locales(signup.service_language)[1]
    with (translation.override(signup.get_service_language_pk())):
        event_name = signup.registration.event.name

    with translation.override(linked_registrations_ui_locale):
        notification_subjects = {
            SignUpNotificationType.CANCELLATION: _(
                "Registration cancelled - %(event_name)s"
            )
            % {"event_name": event_name},
            SignUpNotificationType.CONFIRMATION: _(
                "Registration confirmation - %(event_name)s"
            )
            % {"event_name": event_name},
            SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST: _(
                "Waiting list seat reserved - %(event_name)s"
            )
            % {"event_name": event_name},
            SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT: _(
                "Registration confirmation - %(event_name)s"
            )
            % {"event_name": event_name},
        }

    return notification_subjects[notification_type]


def get_signup_notification_variables(signup):
    [linked_events_ui_locale, linked_registrations_ui_locale] = get_ui_locales(
        signup.service_language
    )
    signup_edit_url = get_signup_edit_url(signup, linked_registrations_ui_locale)

    with (translation.override(signup.get_service_language_pk())):
        event_name = signup.registration.event.name
        event_type_id = signup.registration.event.type_id

        email_variables = {
            "event_name": event_name,
            "event_type_id": event_type_id,
            "linked_events_ui_locale": linked_events_ui_locale,
            "linked_events_ui_url": settings.LINKED_EVENTS_UI_URL,
            "linked_registrations_ui_locale": linked_registrations_ui_locale,
            "linked_registrations_ui_url": settings.LINKED_REGISTRATIONS_UI_URL,
            "registration_id": signup.registration.id,
            "signup_edit_url": signup_edit_url,
            "username": signup.first_name,
        }

    return email_variables
