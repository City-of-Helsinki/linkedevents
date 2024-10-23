from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from events.models import Event
from registrations.utils import get_signup_edit_url, get_ui_locales

CONFIRMATION_HEADING_WITH_USERNAME = _("Welcome %(username)s")
CONFIRMATION_HEADING_WITHOUT_USERNAME = _("Welcome")
CONFIRMATION_TO_WAITING_LIST_HEADING = _(
    "Thank you for signing up for the waiting list"
)
CONFIRMATION_WITH_PAYMENT_HEADING = _(
    "Payment required for registration confirmation - %(event_name)s"
)
CONFIRMATION_WITH_PAYMENT_HEADING_RECURRING = _(
    "Payment required for registration confirmation - Recurring: %(event_name)s"
)
EVENT_CANCELLED_TEXT = _("Thank you for your interest in the event.")
PAYMENT_EXPIRED_HEADING = _("Registration payment expired")
REGISTRATION_CANCELLED_HEADING = _("Registration cancelled")


class NotificationType:
    NO_NOTIFICATION = "none"
    SMS = "sms"
    EMAIL = "email"
    SMS_EMAIL = "sms and email"


NOTIFICATION_TYPES = (
    (NotificationType.NO_NOTIFICATION, _("No Notification")),
    (NotificationType.SMS, _("SMS")),
    (NotificationType.EMAIL, _("E-Mail")),
    (NotificationType.SMS_EMAIL, _("Both SMS and email.")),
)


class SignUpNotificationType:
    EVENT_CANCELLATION = "event_cancellation"
    CANCELLATION = "cancellation"
    CONFIRMATION = "confirmation"
    CONFIRMATION_WITH_PAYMENT = "confirmation_with_payment"
    CONFIRMATION_TO_WAITING_LIST = "confirmation_to_waiting_list"
    TRANSFERRED_AS_PARTICIPANT = "transferred_as_participant"
    TRANSFER_AS_PARTICIPANT_WITH_PAYMENT = "transfer_as_participant_with_payment"
    PAYMENT_EXPIRED = "payment_expired"


signup_notification_subjects = {
    SignUpNotificationType.EVENT_CANCELLATION: _("Event cancelled - %(event_name)s"),
    SignUpNotificationType.CANCELLATION: _("Registration cancelled - %(event_name)s"),
    SignUpNotificationType.CONFIRMATION: _(
        "Registration confirmation - %(event_name)s"
    ),
    SignUpNotificationType.CONFIRMATION_WITH_PAYMENT: CONFIRMATION_WITH_PAYMENT_HEADING,
    SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST: _(
        "Waiting list seat reserved - %(event_name)s"
    ),
    SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT: _(
        "Registration confirmation - %(event_name)s"
    ),
    SignUpNotificationType.TRANSFER_AS_PARTICIPANT_WITH_PAYMENT: CONFIRMATION_WITH_PAYMENT_HEADING,  # noqa: E501
    SignUpNotificationType.PAYMENT_EXPIRED: _(
        "Registration payment expired - %(event_name)s"
    ),
}


signup_email_texts = {
    SignUpNotificationType.EVENT_CANCELLATION: {
        "heading": _("Event %(event_name)s has been cancelled"),
        "text": EVENT_CANCELLED_TEXT,
        "sub_event_cancellation": {
            "heading": _("Event %(event_name)s %(event_period)s has been cancelled"),
        },
    },
    SignUpNotificationType.CANCELLATION: {
        "heading": REGISTRATION_CANCELLED_HEADING,
        "secondary_heading": {
            Event.TypeId.GENERAL: _(
                "%(username)s, registration to the event %(event_name)s has been cancelled."  # noqa: E501
            ),
            Event.TypeId.COURSE: _(
                "%(username)s, registration to the course %(event_name)s has been cancelled."  # noqa: E501
            ),
            Event.TypeId.VOLUNTEERING: _(
                "%(username)s, registration to the volunteering %(event_name)s has been cancelled."  # noqa: E501
            ),
        },
        "secondary_heading_without_username": {
            Event.TypeId.GENERAL: _(
                "Registration to the event %(event_name)s has been cancelled."
            ),
            Event.TypeId.COURSE: _(
                "Registration to the course %(event_name)s has been cancelled."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Registration to the volunteering %(event_name)s has been cancelled."
            ),
        },
        "text": {
            Event.TypeId.GENERAL: _(
                "You have successfully cancelled your registration to the event <strong>%(event_name)s</strong>."  # noqa: E501
            ),
            Event.TypeId.COURSE: _(
                "You have successfully cancelled your registration to the course <strong>%(event_name)s</strong>."  # noqa: E501
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You have successfully cancelled your registration to the volunteering <strong>%(event_name)s</strong>."  # noqa: E501
            ),
        },
        "payment_cancelled": {
            "text": {
                Event.TypeId.GENERAL: _(
                    "Your registration and payment for the event <strong>%(event_name)s</strong> have been cancelled."  # noqa: E501
                ),
                Event.TypeId.COURSE: _(
                    "Your registration and payment for the course <strong>%(event_name)s</strong> have been cancelled."  # noqa: E501
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "Your registration to the volunteering <strong>%(event_name)s</strong> has been cancelled."  # noqa: E501
                ),
            },
        },
        "payment_refunded": {
            "text": {
                Event.TypeId.GENERAL: _(
                    "You have successfully cancelled your registration to the event "
                    "<strong>%(event_name)s</strong>. Your payment for the registration "  # noqa: E501
                    "has been refunded."
                ),
                Event.TypeId.COURSE: _(
                    "You have successfully cancelled your registration to the course "
                    "<strong>%(event_name)s</strong>. Your payment for the registration "  # noqa: E501
                    "has been refunded."
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "You have successfully cancelled your registration to the volunteering "  # noqa: E501
                    "<strong>%(event_name)s</strong>. Your payment for the registration "  # noqa: E501
                    "has been refunded."
                ),
            },
        },
        "payment_partially_refunded": {
            "text": {
                Event.TypeId.GENERAL: _(
                    "You have successfully cancelled a registration to the event "
                    "<strong>%(event_name)s</strong>. Your payment has been partially refunded "  # noqa: E501
                    "for the amount of the cancelled registration."
                ),
                Event.TypeId.COURSE: _(
                    "You have successfully cancelled a registration to the course "
                    "<strong>%(event_name)s</strong>. Your payment has been partially refunded "  # noqa: E501
                    "for the amount of the cancelled registration."
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "You have successfully cancelled a registration to the volunteering "  # noqa: E501
                    "<strong>%(event_name)s</strong>. Your payment has been partially refunded "  # noqa: E501
                    "for the amount of the cancelled registration."
                ),
            },
        },
    },
    SignUpNotificationType.CONFIRMATION: {
        "heading": CONFIRMATION_HEADING_WITH_USERNAME,
        "heading_without_username": CONFIRMATION_HEADING_WITHOUT_USERNAME,
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
                "Congratulations! Your registration has been confirmed for the event <strong>%(event_name)s</strong>."  # noqa: E501
            ),
            Event.TypeId.COURSE: _(
                "Congratulations! Your registration has been confirmed for the course <strong>%(event_name)s</strong>."  # noqa: E501
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Congratulations! Your registration has been confirmed for the volunteering <strong>%(event_name)s</strong>."  # noqa E501
            ),
        },
        "group": {
            "heading": CONFIRMATION_HEADING_WITHOUT_USERNAME,
            "secondary_heading": {
                Event.TypeId.GENERAL: _(
                    "Group registration to the event %(event_name)s has been saved."
                ),
                Event.TypeId.COURSE: _(
                    "Group registration to the course %(event_name)s has been saved."
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "Group registration to the volunteering %(event_name)s has been saved."  # noqa: E501
                ),
            },
        },
    },
    SignUpNotificationType.CONFIRMATION_WITH_PAYMENT: {
        "heading": CONFIRMATION_HEADING_WITH_USERNAME,
        "heading_without_username": CONFIRMATION_HEADING_WITHOUT_USERNAME,
        "secondary_heading": {
            Event.TypeId.GENERAL: _(
                "Payment is required to confirm your registration to the event %(event_name)s."  # noqa: E501
            ),
            Event.TypeId.COURSE: _(
                "Payment is required to confirm your registration to the course %(event_name)s."  # noqa: E501
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Payment is required to confirm your registration to the volunteering "
                "%(event_name)s."
            ),
        },
        "text": {
            Event.TypeId.GENERAL: _(
                "Please use the payment link to confirm your registration for the event "  # noqa: E501
                "<strong>%(event_name)s</strong>. The payment link expires in "
                "%(expiration_hours)s hours."
            ),
            Event.TypeId.COURSE: _(
                "Please use the payment link to confirm your registration for the course "  # noqa: E501
                "<strong>%(event_name)s</strong>. The payment link expires in "
                "%(expiration_hours)s hours."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Please use the payment link to confirm your registration for the volunteering "  # noqa: E501
                "<strong>%(event_name)s</strong>. The payment link expires in "
                "%(expiration_hours)s hours."
            ),
        },
        "group": {
            "heading": CONFIRMATION_HEADING_WITHOUT_USERNAME,
            "secondary_heading": {
                Event.TypeId.GENERAL: _(
                    "Payment is required to confirm your group registration to the event "  # noqa: E501
                    "%(event_name)s."
                ),
                Event.TypeId.COURSE: _(
                    "Payment is required to confirm your group registration to the course "  # noqa: E501
                    "%(event_name)s."
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "Payment is required to confirm your group registration to the volunteering "  # noqa: E501
                    "%(event_name)s."
                ),
            },
        },
    },
    SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST: {
        "heading": CONFIRMATION_TO_WAITING_LIST_HEADING,
        "text": {
            Event.TypeId.GENERAL: _(
                "You have successfully registered for the event <strong>%(event_name)s</strong> waiting list."  # noqa: E501
            ),
            Event.TypeId.COURSE: _(
                "You have successfully registered for the course <strong>%(event_name)s</strong> waiting list."  # noqa: E501
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You have successfully registered for the volunteering <strong>%(event_name)s</strong> waiting list."  # noqa: E501
            ),
        },
        "secondary_text": {
            Event.TypeId.GENERAL: _(
                "You will be automatically transferred as an event participant if a seat becomes available."  # noqa: E501
            ),
            Event.TypeId.COURSE: _(
                "You will be automatically transferred as a course participant if a seat becomes available."  # noqa: E501
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You will be automatically transferred as a volunteering participant if a seat becomes available."  # noqa: E501
            ),
        },
        "group": {
            "text": {
                Event.TypeId.GENERAL: _(
                    "The registration for the event <strong>%(event_name)s</strong> waiting list was successful."  # noqa: E501
                ),
                Event.TypeId.COURSE: _(
                    "The registration for the course <strong>%(event_name)s</strong> waiting list was successful."  # noqa: E501
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "The registration for the volunteering <strong>%(event_name)s</strong> waiting list was successful."  # noqa: E501
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
        "heading": CONFIRMATION_HEADING_WITH_USERNAME,
        "heading_without_username": CONFIRMATION_HEADING_WITHOUT_USERNAME,
        "text": {
            Event.TypeId.GENERAL: _(
                "You have been moved from the waiting list of the event "
                "<strong>%(event_name)s</strong> to a participant."
            ),
            Event.TypeId.COURSE: _(
                "You have been moved from the waiting list of the course "
                "<strong>%(event_name)s</strong> to a participant."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You have been moved from the waiting list of the volunteering "
                "<strong>%(event_name)s</strong> to a participant."
            ),
        },
    },
    SignUpNotificationType.TRANSFER_AS_PARTICIPANT_WITH_PAYMENT: {
        "heading": CONFIRMATION_HEADING_WITH_USERNAME,
        "heading_without_username": CONFIRMATION_HEADING_WITHOUT_USERNAME,
        "text": {
            Event.TypeId.GENERAL: _(
                "You have been selected to be moved from the waiting list of the event "
                "<strong>%(event_name)s</strong> to a participant. Please use the "
                "payment link to confirm your participation. The payment link expires in "  # noqa: E501
                "%(expiration_hours)s hours."
            ),
            Event.TypeId.COURSE: _(
                "You have been selected to be moved from the waiting list of the course "  # noqa: E501
                "<strong>%(event_name)s</strong> to a participant. Please use the "
                "payment link to confirm your participation. The payment link expires in "  # noqa: E501
                "%(expiration_hours)s hours."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You have been selected to be moved from the waiting list of the volunteering "  # noqa: E501
                "<strong>%(event_name)s</strong> to a participant. Please use the "
                "payment link to confirm your participation. The payment link expires in "  # noqa: E501
                "%(expiration_hours)s hours."
            ),
        },
    },
    SignUpNotificationType.PAYMENT_EXPIRED: {
        "heading": PAYMENT_EXPIRED_HEADING,
        "secondary_heading": {
            Event.TypeId.GENERAL: _(
                "Registration to the event %(event_name)s has been cancelled due to an expired "  # noqa: E501
                "payment."
            ),
            Event.TypeId.COURSE: _(
                "Registration to the course %(event_name)s has been cancelled due to an expired "  # noqa: E501
                "payment."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Registration to the volunteering %(event_name)s has been cancelled due to an "  # noqa: E501
                "expired payment."
            ),
        },
        "text": {
            Event.TypeId.GENERAL: _(
                "Your registration to the event <strong>%(event_name)s</strong> has been "  # noqa: E501
                "cancelled due no payment received within the payment period."
            ),
            Event.TypeId.COURSE: _(
                "Your registration to the course <strong>%(event_name)s</strong> has been "  # noqa: E501
                "cancelled due no payment received within the payment period."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Your registration to the volunteering <strong>%(event_name)s</strong> has been "  # noqa: E501
                "cancelled due no payment received within the payment period."
            ),
        },
    },
}


recurring_event_signup_notification_subjects = {
    SignUpNotificationType.EVENT_CANCELLATION: _(
        "Event cancelled - Recurring: %(event_name)s"
    ),
    SignUpNotificationType.CANCELLATION: _(
        "Registration cancelled - Recurring: %(event_name)s"
    ),
    SignUpNotificationType.CONFIRMATION: _(
        "Registration confirmation - Recurring: %(event_name)s"
    ),
    SignUpNotificationType.CONFIRMATION_WITH_PAYMENT: CONFIRMATION_WITH_PAYMENT_HEADING_RECURRING,  # noqa: E501
    SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST: _(
        "Waiting list seat reserved - Recurring: %(event_name)s"
    ),
    SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT: _(
        "Registration confirmation - Recurring: %(event_name)s"
    ),
    SignUpNotificationType.TRANSFER_AS_PARTICIPANT_WITH_PAYMENT: CONFIRMATION_WITH_PAYMENT_HEADING_RECURRING,  # noqa: E501
    SignUpNotificationType.PAYMENT_EXPIRED: _(
        "Registration payment expired - Recurring: %(event_name)s"
    ),
}


recurring_event_signup_email_texts = {
    SignUpNotificationType.EVENT_CANCELLATION: {
        "heading": _(
            "Recurring event %(event_name)s %(event_period)s has been cancelled"
        ),
        "text": EVENT_CANCELLED_TEXT,
    },
    SignUpNotificationType.CANCELLATION: {
        "heading": REGISTRATION_CANCELLED_HEADING,
        "secondary_heading": {
            Event.TypeId.GENERAL: _(
                "%(username)s, registration to the recurring event %(event_name)s "
                "%(event_period)s has been cancelled."
            ),
            Event.TypeId.COURSE: _(
                "%(username)s, registration to the recurring course %(event_name)s "
                "%(event_period)s has been cancelled."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "%(username)s, registration to the recurring volunteering %(event_name)s "  # noqa: E501
                "%(event_period)s has been cancelled."
            ),
        },
        "secondary_heading_without_username": {
            Event.TypeId.GENERAL: _(
                "Registration to the recurring event %(event_name)s %(event_period)s "
                "has been cancelled."
            ),
            Event.TypeId.COURSE: _(
                "Registration to the recurring course %(event_name)s %(event_period)s "
                "has been cancelled."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Registration to the recurring volunteering %(event_name)s %(event_period)s "  # noqa: E501
                "has been cancelled."
            ),
        },
        "text": {
            Event.TypeId.GENERAL: _(
                "You have successfully cancelled your registration to the recurring event "  # noqa: E501
                "<strong>%(event_name)s %(event_period)s</strong>."
            ),
            Event.TypeId.COURSE: _(
                "You have successfully cancelled your registration to the recurring course "  # noqa: E501
                "<strong>%(event_name)s %(event_period)s</strong>."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You have successfully cancelled your registration to the recurring volunteering "  # noqa: E501
                "<strong>%(event_name)s %(event_period)s</strong>."
            ),
        },
        "payment_cancelled": {
            "text": {
                Event.TypeId.GENERAL: _(
                    "Your registration and payment for the recurring event "
                    "<strong>%(event_name)s %(event_period)s</strong> have been cancelled."  # noqa: E501
                ),
                Event.TypeId.COURSE: _(
                    "Your registration and payment for the recurring course "
                    "<strong>%(event_name)s %(event_period)s</strong> have been cancelled."  # noqa: E501
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "Your registration to the recurring volunteering "
                    "<strong>%(event_name)s %(event_period)s</strong> has been cancelled."  # noqa: E501
                ),
            },
        },
        "payment_refunded": {
            "text": {
                Event.TypeId.GENERAL: _(
                    "You have successfully cancelled your registration to the recurring "  # noqa: E501
                    "event <strong>%(event_name)s %(event_period)s</strong>. "
                    "Your payment for the registration has been refunded."
                ),
                Event.TypeId.COURSE: _(
                    "You have successfully cancelled your registration to the recurring "  # noqa: E501
                    "course <strong>%(event_name)s %(event_period)s</strong>. "
                    "Your payment for the registration has been refunded."
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "You have successfully cancelled your registration to the recurring "  # noqa: E501
                    "volunteering <strong>%(event_name)s %(event_period)s</strong>. "
                    "Your payment for the registration has been refunded."
                ),
            },
        },
        "payment_partially_refunded": {
            "text": {
                Event.TypeId.GENERAL: _(
                    "You have successfully cancelled a registration to the recurring event "  # noqa: E501
                    "<strong>%(event_name)s %(event_period)s</strong>. Your payment has been "  # noqa: E501
                    "partially refunded for the amount of the cancelled registration."
                ),
                Event.TypeId.COURSE: _(
                    "You have successfully cancelled a registration to the recurring course "  # noqa: E501
                    "<strong>%(event_name)s %(event_period)s</strong>. Your payment has been "  # noqa: E501
                    "partially refunded for the amount of the cancelled registration."
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "You have successfully cancelled a registration to the recurring volunteering "  # noqa: E501
                    "<strong>%(event_name)s %(event_period)s</strong>. Your payment has been "  # noqa: E501
                    "partially refunded for the amount of the cancelled registration."
                ),
            },
        },
    },
    SignUpNotificationType.CONFIRMATION: {
        "heading": CONFIRMATION_HEADING_WITH_USERNAME,
        "heading_without_username": CONFIRMATION_HEADING_WITHOUT_USERNAME,
        "secondary_heading": {
            Event.TypeId.GENERAL: _(
                "Registration to the recurring event %(event_name)s %(event_period)s "
                "has been saved."
            ),
            Event.TypeId.COURSE: _(
                "Registration to the recurring course %(event_name)s %(event_period)s "
                "has been saved."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Registration to the recurring volunteering %(event_name)s %(event_period)s "  # noqa: E501
                "has been saved."
            ),
        },
        "text": {
            Event.TypeId.GENERAL: _(
                "Congratulations! Your registration has been confirmed for the recurring event "  # noqa: E501
                "<strong>%(event_name)s %(event_period)s</strong>."
            ),
            Event.TypeId.COURSE: _(
                "Congratulations! Your registration has been confirmed for the recurring course "  # noqa: E501
                "<strong>%(event_name)s %(event_period)s</strong>."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Congratulations! Your registration has been confirmed for the recurring "  # noqa: E501
                "volunteering <strong>%(event_name)s %(event_period)s</strong>."
            ),
        },
        "group": {
            "heading": CONFIRMATION_HEADING_WITHOUT_USERNAME,
            "secondary_heading": {
                Event.TypeId.GENERAL: _(
                    "Group registration to the recurring event %(event_name)s %(event_period)s "  # noqa: E501
                    "has been saved."
                ),
                Event.TypeId.COURSE: _(
                    "Group registration to the recurring course %(event_name)s %(event_period)s "  # noqa: E501
                    "has been saved."
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "Group registration to the recurring volunteering %(event_name)s "
                    "%(event_period)s has been saved."
                ),
            },
        },
    },
    SignUpNotificationType.CONFIRMATION_WITH_PAYMENT: {
        "heading": CONFIRMATION_HEADING_WITH_USERNAME,
        "heading_without_username": CONFIRMATION_HEADING_WITHOUT_USERNAME,
        "secondary_heading": {
            Event.TypeId.GENERAL: _(
                "Payment is required to confirm your registration to the recurring event "  # noqa: E501
                "%(event_name)s %(event_period)s."
            ),
            Event.TypeId.COURSE: _(
                "Payment is required to confirm your registration to the recurring course "  # noqa: E501
                "%(event_name)s %(event_period)s."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Payment is required to confirm your registration to the recurring volunteering "  # noqa: E501
                "%(event_name)s %(event_period)s."
            ),
        },
        "text": {
            Event.TypeId.GENERAL: _(
                "Please use the payment link to confirm your registration for the recurring event "  # noqa: E501
                "<strong>%(event_name)s %(event_period)s</strong>. The payment link expires in "  # noqa: E501
                "%(expiration_hours)s hours."
            ),
            Event.TypeId.COURSE: _(
                "Please use the payment link to confirm your registration for the recurring course "  # noqa: E501
                "<strong>%(event_name)s %(event_period)s</strong>. The payment link expires in "  # noqa: E501
                "%(expiration_hours)s hours."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Please use the payment link to confirm your registration for the recurring "  # noqa: E501
                "volunteering <strong>%(event_name)s %(event_period)s</strong>. The payment link "  # noqa: E501
                "expires in %(expiration_hours)s hours."
            ),
        },
        "group": {
            "heading": CONFIRMATION_HEADING_WITHOUT_USERNAME,
            "secondary_heading": {
                Event.TypeId.GENERAL: _(
                    "Payment is required to confirm your group registration to the recurring "  # noqa: E501
                    "event %(event_name)s %(event_period)s."
                ),
                Event.TypeId.COURSE: _(
                    "Payment is required to confirm your group registration to the recurring "  # noqa: E501
                    "course %(event_name)s %(event_period)s."
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "Payment is required to confirm your group registration to the recurring "  # noqa: E501
                    "volunteering %(event_name)s %(event_period)s."
                ),
            },
        },
    },
    SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST: {
        "heading": CONFIRMATION_TO_WAITING_LIST_HEADING,
        "text": {
            Event.TypeId.GENERAL: _(
                "You have successfully registered for the recurring event "
                "<strong>%(event_name)s %(event_period)s</strong> waiting list."
            ),
            Event.TypeId.COURSE: _(
                "You have successfully registered for the recurring course "
                "<strong>%(event_name)s %(event_period)s</strong> waiting list."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You have successfully registered for the recurring volunteering "
                "<strong>%(event_name)s %(event_period)s</strong> waiting list."
            ),
        },
        "secondary_text": signup_email_texts[
            SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST
        ]["secondary_text"],
        "group": {
            "text": {
                Event.TypeId.GENERAL: _(
                    "The registration for the recurring event "
                    "<strong>%(event_name)s %(event_period)s</strong> waiting list was successful."  # noqa: E501
                ),
                Event.TypeId.COURSE: _(
                    "The registration for the recurring course "
                    "<strong>%(event_name)s %(event_period)s</strong> waiting list was successful."  # noqa: E501
                ),
                Event.TypeId.VOLUNTEERING: _(
                    "The registration for the recurring volunteering "
                    "<strong>%(event_name)s %(event_period)s</strong> waiting list was successful."  # noqa: E501
                ),
            },
            "secondary_text": signup_email_texts[
                SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST
            ]["group"]["secondary_text"],
        },
    },
    SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT: {
        "heading": CONFIRMATION_HEADING_WITH_USERNAME,
        "heading_without_username": CONFIRMATION_HEADING_WITHOUT_USERNAME,
        "text": {
            Event.TypeId.GENERAL: _(
                "You have been moved from the waiting list of the recurring event "
                "<strong>%(event_name)s %(event_period)s</strong> to a participant."
            ),
            Event.TypeId.COURSE: _(
                "You have been moved from the waiting list of the recurring course "
                "<strong>%(event_name)s %(event_period)s</strong> to a participant."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You have been moved from the waiting list of the recurring volunteering "  # noqa: E501
                "<strong>%(event_name)s %(event_period)s</strong> to a participant."
            ),
        },
    },
    SignUpNotificationType.TRANSFER_AS_PARTICIPANT_WITH_PAYMENT: {
        "heading": CONFIRMATION_HEADING_WITH_USERNAME,
        "heading_without_username": CONFIRMATION_HEADING_WITHOUT_USERNAME,
        "text": {
            Event.TypeId.GENERAL: _(
                "You have been selected to be moved from the waiting list of the recurring "  # noqa: E501
                "event <strong>%(event_name)s %(event_period)s</strong> to a participant. "  # noqa: E501
                "Please use the payment link to confirm your participation. The payment link "  # noqa: E501
                "expires in %(expiration_hours)s hours."
            ),
            Event.TypeId.COURSE: _(
                "You have been selected to be moved from the waiting list of the recurring "  # noqa: E501
                "course <strong>%(event_name)s %(event_period)s</strong> to a participant. "  # noqa: E501
                "Please use the payment link to confirm your participation. The payment link "  # noqa: E501
                "expires in %(expiration_hours)s hours."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "You have been selected to be moved from the waiting list of the recurring "  # noqa: E501
                "volunteering <strong>%(event_name)s %(event_period)s</strong> to a participant. "  # noqa: E501
                "Please use the payment link to confirm your participation. The payment link "  # noqa: E501
                "expires in %(expiration_hours)s hours."
            ),
        },
    },
    SignUpNotificationType.PAYMENT_EXPIRED: {
        "heading": PAYMENT_EXPIRED_HEADING,
        "secondary_heading": {
            Event.TypeId.GENERAL: _(
                "Registration to the recurring event %(event_name)s %(event_period)s "
                "has been cancelled due to an expired payment."
            ),
            Event.TypeId.COURSE: _(
                "Registration to the recurring course %(event_name)s %(event_period)s "
                "has been cancelled due to an expired payment."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Registration to the recurring volunteering %(event_name)s %(event_period)s "  # noqa: E501
                "has been cancelled due to an expired payment."
            ),
        },
        "text": {
            Event.TypeId.GENERAL: _(
                "Your registration to the recurring event "
                "<strong>%(event_name)s %(event_period)s</strong> has been cancelled due no "  # noqa: E501
                "payment received within the payment period."
            ),
            Event.TypeId.COURSE: _(
                "Your registration to the recurring course "
                "<strong>%(event_name)s %(event_period)s</strong> has been cancelled due no "  # noqa: E501
                "payment received within the payment period."
            ),
            Event.TypeId.VOLUNTEERING: _(
                "Your registration to the recurring volunteering "
                "<strong>%(event_name)s %(event_period)s</strong> has been cancelled due no "  # noqa: E501
                "payment received within the payment period."
            ),
        },
    },
}


registration_user_access_invitation_subjects = {
    "registration_user_access": _(
        "Rights granted to the participant list - %(event_name)s"
    ),
    "registration_substitute_user": _(
        "Rights granted to the registration - %(event_name)s"
    ),
}


registration_user_access_invitation_texts = {
    "registration_user_access": {
        "text": {
            Event.TypeId.GENERAL: _(
                "The e-mail address <strong>%(email)s</strong> has been granted the rights to "  # noqa: E501
                "read the participant list of the event <strong>%(event_name)s</strong>. Using "  # noqa: E501
                "the Suomi.fi identification is required to be able to read the participant list."  # noqa: E501
            ),
            Event.TypeId.COURSE: _(
                "The e-mail address <strong>%(email)s</strong> has been granted the rights to "  # noqa: E501
                "read the participant list of the course <strong>%(event_name)s</strong>. Using "  # noqa: E501
                "the Suomi.fi identification is required to be able to read the participant list."  # noqa: E501
            ),
            Event.TypeId.VOLUNTEERING: _(
                "The e-mail address <strong>%(email)s</strong> has been granted the rights to "  # noqa: E501
                "read the participant list of the volunteering <strong>%(event_name)s</strong>. "  # noqa: E501
                "Using the Suomi.fi identification is required to be able to read the participant "  # noqa: E501
                "list."
            ),
        }
    },
    "registration_substitute_user": {
        "text": {
            Event.TypeId.GENERAL: _(
                "The e-mail address <strong>%(email)s</strong> has been granted substitute user rights to the registration of the event <strong>%(event_name)s</strong>."  # noqa E501
            ),
            Event.TypeId.COURSE: _(
                "The e-mail address <strong>%(email)s</strong> has been granted substitute user rights to the registration of the course <strong>%(event_name)s</strong>."  # noqa E501
            ),
            Event.TypeId.VOLUNTEERING: _(
                "The e-mail address <strong>%(email)s</strong> has been granted substitute user rights to the registration of the volunteering <strong>%(event_name)s</strong>."  # noqa E501
            ),
        }
    },
}


def _get_event_text_kwargs(event_name, event_period=None, notification_type=None):
    kwargs = {"event_name": event_name}

    if event_period is not None:
        kwargs["event_period"] = event_period

    if notification_type is not None and notification_type in (
        SignUpNotificationType.CONFIRMATION_WITH_PAYMENT,
        SignUpNotificationType.TRANSFER_AS_PARTICIPANT_WITH_PAYMENT,
    ):
        kwargs["expiration_hours"] = settings.WEB_STORE_ORDER_EXPIRATION_HOURS

    return kwargs


def _get_event_cancellation_texts(
    text_options, event_name, event_period, is_sub_event_cancellation=False
):
    event_text_kwargs = _get_event_text_kwargs(event_name, event_period=event_period)

    if is_sub_event_cancellation:
        texts = {
            "heading": text_options["sub_event_cancellation"]["heading"]
            % event_text_kwargs,
        }
    else:
        texts = {
            "heading": text_options["heading"] % event_text_kwargs,
        }

    texts["text"] = text_options["text"]

    return texts


def _get_notification_texts(
    text_options,
    event_type_id,
    event_name,
    event_period,
    contact_person,
    notification_type,
):
    event_text_kwargs = _get_event_text_kwargs(
        event_name, event_period=event_period, notification_type=notification_type
    )

    if contact_person.first_name:
        texts = {
            "heading": text_options["heading"]
            % {"username": contact_person.first_name},
        }
    else:
        texts = {
            "heading": text_options.get(
                "heading_without_username", text_options["heading"]
            ),
        }

    texts["text"] = text_options["text"][event_type_id] % event_text_kwargs

    return texts


def _format_confirmation_message_texts(texts, confirmation_message):
    if confirmation_message:
        texts["confirmation_message"] = confirmation_message


def _format_cancellation_texts(
    texts,
    text_options,
    event_type_id,
    event_name,
    event_period,
    contact_person,
    payment_refunded=False,
    payment_partially_refunded=False,
    payment_cancelled=False,
):
    event_text_kwargs = _get_event_text_kwargs(event_name, event_period=event_period)

    if contact_person.first_name:
        texts["secondary_heading"] = text_options["secondary_heading"][
            event_type_id
        ] % {
            **event_text_kwargs,
            "username": contact_person.first_name,
        }
    else:
        texts["secondary_heading"] = (
            text_options["secondary_heading_without_username"][event_type_id]
            % event_text_kwargs
        )

    if payment_partially_refunded:
        texts["text"] = (
            text_options["payment_partially_refunded"]["text"][event_type_id]
            % event_text_kwargs
        )
    elif payment_refunded:
        texts["text"] = (
            text_options["payment_refunded"]["text"][event_type_id] % event_text_kwargs
        )
    elif payment_cancelled:
        texts["text"] = (
            text_options["payment_cancelled"]["text"][event_type_id] % event_text_kwargs
        )


def _format_confirmation_texts(
    texts, text_options, event_type_id, event_name, event_period, contact_person
):
    event_text_kwargs = _get_event_text_kwargs(event_name, event_period=event_period)

    if contact_person.signup_group_id:
        # Override default confirmation message heading
        texts["heading"] = text_options["group"]["heading"]
        texts["secondary_heading"] = (
            text_options["group"]["secondary_heading"][event_type_id]
            % event_text_kwargs
        )
    else:
        texts["secondary_heading"] = (
            text_options["secondary_heading"][event_type_id] % event_text_kwargs
        )


def _format_confirmation_to_waiting_list_texts(
    texts, text_options, event_type_id, event_name, event_period, contact_person
):
    if contact_person.signup_group_id:
        # Override default confirmation message heading
        event_text_kwargs = _get_event_text_kwargs(
            event_name, event_period=event_period
        )
        texts["text"] = text_options["group"]["text"][event_type_id] % event_text_kwargs
        texts["secondary_text"] = text_options["group"]["secondary_text"][event_type_id]
    else:
        texts["secondary_text"] = text_options["secondary_text"][event_type_id]


def _format_payment_expiration_texts(
    texts, text_options, event_type_id, event_name, event_period
):
    event_text_kwargs = _get_event_text_kwargs(event_name, event_period=event_period)

    texts["secondary_heading"] = (
        text_options["secondary_heading"][event_type_id] % event_text_kwargs
    )


def get_signup_notification_texts(
    contact_person,
    notification_type: SignUpNotificationType,
    is_sub_event_cancellation=False,
    payment_refunded=False,
    payment_partially_refunded=False,
    payment_cancelled=False,
):
    registration = contact_person.registration
    service_lang = contact_person.get_service_language_pk()
    event_type_id = registration.event.type_id

    with translation.override(service_lang):
        confirmation_message = registration.confirmation_message
        event_name = registration.event.name

    if not is_sub_event_cancellation and registration.event.is_recurring_super_event:
        # Signup or cancellation for a recurring super event.
        text_options = recurring_event_signup_email_texts[notification_type]
        event_period = registration.event.get_start_and_end_time_display(
            lang=service_lang, date_only=True
        )
    else:
        # Signup or cancellation for a normal event (or for a sub-event of a super
        # event).
        text_options = signup_email_texts[notification_type]
        event_period = None

    if notification_type == SignUpNotificationType.EVENT_CANCELLATION:
        sub_event_period = (
            registration.event.get_start_and_end_time_display(
                lang=service_lang, date_only=True
            )
            if is_sub_event_cancellation
            else event_period
        )
        texts = _get_event_cancellation_texts(
            text_options,
            event_name,
            sub_event_period,
            is_sub_event_cancellation=is_sub_event_cancellation,
        )
    else:
        texts = _get_notification_texts(
            text_options,
            event_type_id,
            event_name,
            event_period,
            contact_person,
            notification_type,
        )

    if notification_type == SignUpNotificationType.CANCELLATION:
        _format_cancellation_texts(
            texts,
            text_options,
            event_type_id,
            event_name,
            event_period,
            contact_person,
            payment_refunded=payment_refunded,
            payment_partially_refunded=payment_partially_refunded,
            payment_cancelled=payment_cancelled,
        )
    elif notification_type == SignUpNotificationType.CONFIRMATION:
        _format_confirmation_texts(
            texts, text_options, event_type_id, event_name, event_period, contact_person
        )
        _format_confirmation_message_texts(texts, confirmation_message)
    elif notification_type == SignUpNotificationType.CONFIRMATION_TO_WAITING_LIST:
        _format_confirmation_to_waiting_list_texts(
            texts, text_options, event_type_id, event_name, event_period, contact_person
        )
    elif notification_type == SignUpNotificationType.TRANSFERRED_AS_PARTICIPANT:
        _format_confirmation_message_texts(texts, confirmation_message)
    elif notification_type == SignUpNotificationType.PAYMENT_EXPIRED:
        _format_payment_expiration_texts(
            texts, text_options, event_type_id, event_name, event_period
        )

    return texts


def get_signup_notification_subject(
    contact_person, notification_type, is_sub_event_cancellation=False
):
    registration = contact_person.registration
    linked_registrations_ui_locale = get_ui_locales(contact_person.service_language)[1]

    with translation.override(contact_person.get_service_language_pk()):
        subject_format_kwargs = {"event_name": registration.event.name}

    with translation.override(linked_registrations_ui_locale):
        if (
            not is_sub_event_cancellation
            and registration.event.is_recurring_super_event
        ):
            # Signup or cancellation for a recurring super event.
            subject_format_kwargs["event_period"] = (
                registration.event.get_start_and_end_time_display(
                    lang=linked_registrations_ui_locale, date_only=True
                )
            )
            notification_subject = (
                recurring_event_signup_notification_subjects[notification_type]
                % subject_format_kwargs
            )
        else:
            # Signup or cancellation for a normal event (or for a sub-event of a super
            # event).
            notification_subject = (
                signup_notification_subjects[notification_type] % subject_format_kwargs
            )

    return notification_subject


def get_signup_notification_variables(contact_person, access_code=None):
    [linked_events_ui_locale, linked_registrations_ui_locale] = get_ui_locales(
        contact_person.service_language
    )
    signup_edit_url = get_signup_edit_url(
        contact_person, linked_registrations_ui_locale, access_code=access_code
    )
    registration = contact_person.registration

    with translation.override(contact_person.get_service_language_pk()):
        event_name = registration.event.name
        event_type_id = registration.event.type_id

        email_variables = {
            "event_name": event_name,
            "event_type_id": event_type_id,
            "linked_events_ui_locale": linked_events_ui_locale,
            "linked_events_ui_url": settings.LINKED_EVENTS_UI_URL,
            "linked_registrations_ui_locale": linked_registrations_ui_locale,
            "linked_registrations_ui_url": settings.LINKED_REGISTRATIONS_UI_URL,
            "registration_id": registration.id,
            "signup_edit_url": signup_edit_url,
            "username": contact_person.first_name,
        }

    return email_variables


def get_registration_user_access_invitation_texts(registration_user_access):
    registration = registration_user_access.registration
    language = registration_user_access.get_language_pk()
    event_type_id = registration.event.type_id

    if registration_user_access.is_substitute_user:
        text_options = registration_user_access_invitation_texts[
            "registration_substitute_user"
        ]
    else:
        text_options = registration_user_access_invitation_texts[
            "registration_user_access"
        ]

    with translation.override(language):
        event_name = registration.event.name
        texts = {
            "text": text_options["text"][event_type_id]
            % {
                "email": registration_user_access.email,
                "event_name": event_name,
            }
        }

    return texts


def get_registration_user_access_invitation_subject(registration_user_access):
    registration = registration_user_access.registration
    language = registration_user_access.get_language_pk()

    with translation.override(language):
        event_name = registration.event.name

        if registration_user_access.is_substitute_user:
            subject = registration_user_access_invitation_subjects[
                "registration_substitute_user"
            ]
        else:
            subject = registration_user_access_invitation_subjects[
                "registration_user_access"
            ]

    return subject % {"event_name": event_name}


def get_registration_user_access_invitation_variables(registration_user_access):
    registration = registration_user_access.registration
    language = registration_user_access.get_language_pk()

    if registration_user_access.is_substitute_user:
        base_url = settings.LINKED_EVENTS_UI_URL
        registration_term = "registrations"
    else:
        base_url = settings.LINKED_REGISTRATIONS_UI_URL
        registration_term = "registration"
    participant_list_url = (
        f"{base_url}/{language}/{registration_term}/{registration.pk}/attendance-list/"
    )

    email_variables = {
        "linked_events_ui_locale": language,
        "linked_events_ui_url": settings.LINKED_EVENTS_UI_URL,
        "linked_registrations_ui_url": settings.LINKED_REGISTRATIONS_UI_URL,
        "participant_list_url": participant_list_url,
    }

    return email_variables
