import logging
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from icalendar import Calendar, vText
from icalendar import Event as CalendarEvent
from requests import RequestException

from registrations.exceptions import WebStoreAPIError, WebStoreRefundValidationError
from web_store.merchant.clients import WebStoreMerchantAPIClient
from web_store.order.clients import WebStoreOrderAPIClient
from web_store.payment.clients import WebStorePaymentAPIClient
from web_store.product.clients import WebStoreProductAPIClient

logger = logging.getLogger(__name__)


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


def get_email_noreply_address():
    return (
        settings.DEFAULT_FROM_EMAIL
        or "noreply-linkedevents@%s" % Site.objects.get_current().domain
    )


def has_allowed_substitute_user_email_domain(email_address):
    return email_address and any(
        [
            email_address.endswith(domain)
            for domain in settings.SUBSTITUTE_USER_ALLOWED_EMAIL_DOMAINS
        ]
    )


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


def strip_trailing_zeroes_from_decimal(value: Decimal):
    if value == value.to_integral():
        return value.quantize(Decimal(1))

    return value.normalize()


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


def get_checkout_url_with_lang_param(checkout_url: str, lang_code: str) -> str:
    if "?" in checkout_url:
        return f"{checkout_url}&lang={lang_code}"
    else:
        return f"{checkout_url}?lang={lang_code}"


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


def _get_web_store_api_refunds_error_messages(response_json):
    return [str(error) for error in response_json["errors"]]


def _get_web_store_api_error_message(response):
    error_status_code = getattr(response, "status_code", None)

    try:
        errors = response.json()["errors"]
    except (AttributeError, ValueError, KeyError):
        error_message = _("Unknown Talpa web store API error")
        return f"{error_message} (status_code: {error_status_code})"
    else:
        error_message = _("Talpa web store API error")
        return f"{error_message} (status_code: {error_status_code}): {errors}"


def _raise_web_store_chained_api_exception(request_exc):
    api_error_message = _get_web_store_api_error_message(request_exc.response)
    logger.error(api_error_message)

    status_code = getattr(request_exc.response, "status_code", None)
    raise WebStoreAPIError(
        _("Payment API experienced an error (code: %(status_code)s)")
        % {"status_code": status_code},
        status_code,
    ) from request_exc


def create_web_store_api_order(
    signup_or_group, contact_person, localized_expiration_datetime
):
    user_uuid = (
        signup_or_group.created_by.uuid if signup_or_group.created_by_id else None
    )

    service_lang = getattr(contact_person, "service_language_id", None) or "fi"
    with translation.override(service_lang):
        order_data = signup_or_group.to_web_store_order_json(
            user_uuid, contact_person=contact_person
        )

    order_data["lastValidPurchaseDateTime"] = localized_expiration_datetime.astimezone(
        ZoneInfo("Europe/Helsinki")
    ).strftime("%Y-%m-%dT%H:%M:%S")

    client = WebStoreOrderAPIClient()
    try:
        return client.create_order(order_data)
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)


def create_or_update_web_store_merchant(merchant, created: bool):
    client = WebStoreMerchantAPIClient()

    try:
        if created:
            resp_json = client.create_merchant(merchant.to_web_store_merchant_json())
            merchant.merchant_id = resp_json.get("merchantId")
            merchant.save(update_fields=["merchant_id"])
        else:
            client.update_merchant(
                merchant.merchant_id, merchant.to_web_store_merchant_json()
            )
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)


def create_web_store_refunds(orders_data):
    client = WebStoreOrderAPIClient()

    try:
        resp_json = client.create_instant_refunds(orders_data)
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)
    else:
        if orders_data and len(resp_json.get("errors", [])) == len(orders_data):
            # All refunds have errors => raise exception.
            refund_error_messages = _get_web_store_api_refunds_error_messages(resp_json)
            raise WebStoreRefundValidationError(refund_error_messages)

        return resp_json


def create_web_store_product_mapping(product_mapping_data: dict):
    client = WebStoreProductAPIClient()

    try:
        return client.create_product_mapping(product_mapping_data)
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)


def cancel_web_store_order(payment):
    client = WebStoreOrderAPIClient()
    user = getattr(payment, "created_by", None)

    try:
        return client.cancel_order(
            payment.external_order_id, user_uuid=str(getattr(user, "uuid", ""))
        )
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)


def create_web_store_product_accounting(product_id: str, product_accounting_data: dict):
    client = WebStoreProductAPIClient()

    try:
        return client.create_product_accounting(product_id, product_accounting_data)
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)


def get_web_store_order(order_id: str) -> dict:
    order_api_client = WebStoreOrderAPIClient()

    try:
        return order_api_client.get_order(order_id=order_id)
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)


def get_web_store_payment(order_id: str) -> dict:
    client = WebStorePaymentAPIClient()

    try:
        return client.get_payment(order_id=order_id)
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)


def get_web_store_refund_payments(refund_id: str) -> list[dict]:
    client = WebStorePaymentAPIClient()

    try:
        return client.get_refund_payments(refund_id=refund_id)
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)


def get_web_store_order_status(order_id: str) -> Optional[str]:
    order_json = get_web_store_order(order_id)
    return order_json.get("status")


def get_web_store_payment_status(order_id: str) -> Optional[str]:
    payment_json = get_web_store_payment(order_id)
    return payment_json.get("status")


def get_web_store_refund_payment_status(refund_id: str) -> Optional[str]:
    payments_list = get_web_store_refund_payments(refund_id)
    if payments_list:
        # Even though the API returns a list, it will contain only one payment in our case since  # noqa: E501
        # we create a new refund each time and it will have a single payment
        # created in Talpa.
        return payments_list[0].get("status")

    return None
