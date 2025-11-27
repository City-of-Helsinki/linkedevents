from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.utils import translation
from icalendar import Calendar, vText
from icalendar import Event as CalendarEvent


def _create_calendar_event_from_event(event, time_zone):
    calendar_event = CalendarEvent()

    if (start_time := event.start_time) and (name := event.name):
        calendar_event.add("dtstart", start_time.astimezone(time_zone))
        calendar_event.add("summary", name)
    else:
        raise ValueError(
            "Event doesn't have start_time or name. Ics file cannot be created."
        )

    end_time = event.end_time if event.end_time else start_time
    calendar_event.add("dtend", end_time.astimezone(time_zone))

    if description := event.short_description:
        calendar_event.add("description", description)
    if location := event.location:
        location_parts = [
            location.name,
            location.street_address,
            location.address_locality,
        ]
        location_text = ", ".join([i for i in location_parts if i])
        calendar_event["location"] = vText(location_text)

    return calendar_event


def code_validity_duration(seats):
    return settings.SEAT_RESERVATION_DURATION + seats


def create_events_ics_file_content(events, language="fi"):
    cal = Calendar()

    # Some properties are required to be compliant
    cal.add("prodid", "-//linkedevents.hel.fi//NONSGML API//EN")
    cal.add("version", "2.0")

    local_tz = ZoneInfo(settings.TIME_ZONE)
    with translation.override(language):
        for event in events:
            calendar_event = _create_calendar_event_from_event(event, local_tz)
            cal.add_component(calendar_event)

    return cal.to_ical()


def get_access_code_for_contact_person(contact_person, user):
    if not contact_person:
        return None

    if not user:
        access_code = contact_person.create_access_code()
    else:
        access_code = (
            contact_person.create_access_code()
            if contact_person.can_create_access_code(user)
            else None
        )

    return access_code


def get_email_noreply_address():
    return (
        settings.DEFAULT_FROM_EMAIL
        or f"noreply-linkedevents@{Site.objects.get_current().domain}"
    )


def has_allowed_substitute_user_email_domain(email_address):
    return email_address and any(
        [
            email_address.endswith(domain)
            for domain in settings.SUBSTITUTE_USER_ALLOWED_EMAIL_DOMAINS
        ]
    )


def move_waitlisted_to_attending(registration, count: int):
    """Changes given number of wait-listed attendees in a registration to be attending."""  # noqa: E501
    waitlisted_signups = registration.get_waitlisted(count=count)
    price_groups_exist = (
        settings.WEB_STORE_INTEGRATION_ENABLED
        and registration.registration_price_groups.exists()
    )

    for first_on_list in waitlisted_signups:
        if price_groups_exist:
            registration.move_first_waitlisted_to_attending_with_payment_link(
                first_on_list=first_on_list
            )
        else:
            registration.move_first_waitlisted_to_attending(first_on_list=first_on_list)


def send_mass_html_mail(
    datatuple,
    fail_silently=False,
    auth_user=None,
    auth_password=None,
    connection=None,
):
    """
    django.core.mail.send_mass_mail doesn't support sending html mails.
    """
    num_messages = 0

    for subject, message, html_message, from_email, recipient_list in datatuple:
        num_messages += send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=fail_silently,
            auth_user=auth_user,
            auth_password=auth_password,
            connection=connection,
            html_message=html_message,
        )

    return num_messages


def strip_trailing_zeroes_from_decimal(value: Decimal):
    if value == value.to_integral():
        return value.quantize(Decimal(1))

    return value.normalize()
