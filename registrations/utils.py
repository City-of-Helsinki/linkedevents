from decimal import Decimal

import pytz
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from icalendar import Calendar
from icalendar import Event as CalendarEvent
from icalendar import vText
from requests import RequestException

from registrations.exceptions import WebStoreAPIError, WebStoreRefundValidationError
from web_store.merchant.clients import WebStoreMerchantAPIClient
from web_store.order.clients import WebStoreOrderAPIClient
from web_store.payment.clients import WebStorePaymentAPIClient
from web_store.product.clients import WebStoreProductAPIClient


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
        settings.DEFAULT_FROM_EMAIL or "noreply@%s" % Site.objects.get_current().domain
    )


def has_allowed_substitute_user_email_domain(email_address):
    return email_address and any(
        [
            email_address.endswith(domain)
            for domain in settings.SUBSTITUTE_USER_ALLOWED_EMAIL_DOMAINS
        ]
    )


def create_event_ics_file_content(event, language="fi"):
    cal = Calendar()
    # Some properties are required to be compliant
    cal.add("prodid", "-//linkedevents.hel.fi//NONSGML API//EN")
    cal.add("version", "2.0")

    with translation.override(language):
        calendar_event = CalendarEvent()

        if (start_time := event.start_time) and (name := event.name):
            calendar_event.add("dtstart", start_time)
            calendar_event.add("summary", name)
        else:
            raise ValueError(
                "Event doesn't have start_time or name. Ics file cannot be created."
            )

        calendar_event.add("dtend", event.end_time if event.end_time else start_time)

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

        cal.add_component(calendar_event)

    filename = f"event_{event.id}.ics"

    return filename, cal.to_ical()


def strip_trailing_zeroes_from_decimal(value: Decimal):
    if value == value.to_integral():
        return value.quantize(Decimal(1))

    return value.normalize()


def move_waitlisted_to_attending(registration, count: int):
    """Changes given number of wait-listed attendees in a registration to be attending."""
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


def get_web_store_api_error_message(response):
    error_status_code = getattr(response, "status_code", None)

    try:
        errors = response.json()["errors"]
    except (AttributeError, ValueError, KeyError):
        error_message = _("Unknown Talpa web store API error")
        error = f"{error_message} (status_code: {error_status_code})"
    else:
        error_message = _("Talpa web store API error")
        error = f"{error_message} (status_code: {error_status_code}): {errors}"

    return error


def get_web_store_api_refunds_error_messages(response_json):
    return [str(error) for error in response_json["errors"]]


def create_web_store_api_order(
    signup_or_group, contact_person, localized_expiration_datetime
):
    user_uuid = (
        signup_or_group.created_by.uuid if signup_or_group.created_by_id else None
    )

    service_lang = getattr(contact_person, "service_language_id", "fi")
    with translation.override(service_lang):
        order_data = signup_or_group.to_web_store_order_json(
            user_uuid, contact_person=contact_person
        )

    order_data["lastValidPurchaseDateTime"] = localized_expiration_datetime.astimezone(
        pytz.UTC
    ).strftime("%Y-%m-%dT%H:%M:%S")

    client = WebStoreOrderAPIClient()
    try:
        resp_json = client.create_order(order_data)
    except RequestException as request_exc:
        api_error_message = get_web_store_api_error_message(request_exc.response)
        raise WebStoreAPIError(api_error_message)

    return resp_json


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
        api_error_message = get_web_store_api_error_message(request_exc.response)
        raise WebStoreAPIError(api_error_message)


def create_web_store_refund(payment):
    client = WebStorePaymentAPIClient()

    try:
        resp_json = client.create_instant_refund(payment.external_order_id)
    except RequestException as request_exc:
        if getattr(request_exc.response, "status_code", 0) == 404:
            # Order does not exist so no need to refund => interpret as success.
            # This might otherwise cause unnecessary exceptions in automated refunds.
            return {}

        api_error_message = get_web_store_api_error_message(request_exc.response)
        raise WebStoreAPIError(api_error_message)

    if resp_json.get("errors"):
        # Refund has errors despite a 200/OK status_code => raise exception.
        refund_error_messages = get_web_store_api_refunds_error_messages(resp_json)
        raise WebStoreRefundValidationError(refund_error_messages)

    return resp_json


def create_web_store_refunds(orders_data):
    client = WebStoreOrderAPIClient()

    try:
        resp_json = client.create_instant_refunds(orders_data)
    except RequestException as request_exc:
        api_error_message = get_web_store_api_error_message(request_exc.response)
        raise WebStoreAPIError(api_error_message)

    if orders_data and len(resp_json.get("errors", [])) == len(orders_data):
        # All refunds have errors => raise exception.
        refund_error_messages = get_web_store_api_refunds_error_messages(resp_json)
        raise WebStoreRefundValidationError(refund_error_messages)

    return resp_json


def create_web_store_product_mapping(product_mapping_data: dict):
    client = WebStoreProductAPIClient()

    try:
        resp_json = client.create_product_mapping(product_mapping_data)
    except RequestException as request_exc:
        api_error_message = get_web_store_api_error_message(request_exc.response)
        raise WebStoreAPIError(api_error_message)

    return resp_json


def cancel_web_store_order(payment):
    client = WebStoreOrderAPIClient()
    user = getattr(payment, "created_by", None)

    try:
        resp_json = client.cancel_order(
            payment.external_order_id, user_uuid=str(getattr(user, "uuid", ""))
        )
    except RequestException as request_exc:
        if getattr(request_exc.response, "status_code", 0) == 404:
            # Order does not exist so no need to cancel => interpret as success.
            # This might otherwise cause unnecessary exceptions in automated cancellations.
            return {}

        api_error_message = get_web_store_api_error_message(request_exc.response)
        raise WebStoreAPIError(api_error_message)

    return resp_json


def create_web_store_product_accounting(product_id: str, product_accounting_data: dict):
    client = WebStoreProductAPIClient()

    try:
        resp_json = client.create_product_accounting(
            product_id, product_accounting_data
        )
    except RequestException as request_exc:
        api_error_message = get_web_store_api_error_message(request_exc.response)
        raise WebStoreAPIError(api_error_message)

    return resp_json
