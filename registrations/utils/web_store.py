import logging
from typing import Optional
from zoneinfo import ZoneInfo

from django.utils import translation
from django.utils.translation import gettext_lazy as _
from requests import RequestException

from registrations.exceptions import WebStoreAPIError, WebStoreRefundValidationError
from web_store.merchant.clients import WebStoreMerchantAPIClient
from web_store.order.clients import WebStoreOrderAPIClient
from web_store.payment.clients import WebStorePaymentAPIClient
from web_store.product.clients import WebStoreProductAPIClient

logger = logging.getLogger(__name__)


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


def cancel_web_store_order(payment):
    client = WebStoreOrderAPIClient()
    user = getattr(payment, "created_by", None)

    try:
        return client.cancel_order(
            payment.external_order_id, user_uuid=str(getattr(user, "uuid", ""))
        )
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


def create_web_store_product_accounting(product_id: str, product_accounting_data: dict):
    client = WebStoreProductAPIClient()

    try:
        return client.create_product_accounting(product_id, product_accounting_data)
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)


def create_web_store_product_mapping(product_mapping_data: dict):
    client = WebStoreProductAPIClient()

    try:
        return client.create_product_mapping(product_mapping_data)
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


def get_checkout_url_with_lang_param(checkout_url: str, lang_code: str) -> str:
    if "?" in checkout_url:
        return f"{checkout_url}&lang={lang_code}"
    else:
        return f"{checkout_url}?lang={lang_code}"


def get_web_store_order(order_id: str) -> dict:
    order_api_client = WebStoreOrderAPIClient()

    try:
        return order_api_client.get_order(order_id=order_id)
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)


def get_web_store_order_status(order_id: str) -> Optional[str]:
    order_json = get_web_store_order(order_id)
    return order_json.get("status")


def get_web_store_payment(order_id: str) -> dict:
    client = WebStorePaymentAPIClient()

    try:
        return client.get_payment(order_id=order_id)
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)


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


def get_web_store_refund_payments(refund_id: str) -> list[dict]:
    client = WebStorePaymentAPIClient()

    try:
        return client.get_refund_payments(refund_id=refund_id)
    except RequestException as request_exc:
        _raise_web_store_chained_api_exception(request_exc)
