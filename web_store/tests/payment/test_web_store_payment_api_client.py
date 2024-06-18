import pytest
import requests_mock
from django.conf import settings
from requests import RequestException
from rest_framework import status

from web_store.exceptions import WebStoreImproperlyConfiguredException
from web_store.order.enums import WebStoreOrderRefundStatus
from web_store.payment.clients import WebStorePaymentAPIClient
from web_store.payment.enums import WebStorePaymentStatus
from web_store.tests.order.test_web_store_order_api_client import (
    DEFAULT_ITEM,
    DEFAULT_ORDER_ID,
    DEFAULT_REFUND_ID,
)

DEFAULT_PAYMENT_ID = "fa4e9268-9b06-4574-bfa3-5e0ff5b799a8"

DEFAULT_GET_PAYMENT_DATA = {
    "paymentId": DEFAULT_PAYMENT_ID,
    "namespace": "string",
    "orderId": DEFAULT_ORDER_ID,
    "userId": "string",
    "status": WebStorePaymentStatus.PAID.value,
    "paymentMethod": "string",
    "paymentType": "string",
    "totalExclTax": "80.65",
    "total": "100.00",
    "taxAmount": "19.35",
    "description": "string",
    "additionalInfo": "string",
    "token": "string",
    "timestamp": "2024-02-01T12:00:00Z",
    "paymentMethodLabel": "string",
}

DEFAULT_GET_REFUND_PAYMENT_DATA = {
    "refundPaymentId": "string",
    "orderId": DEFAULT_ORDER_ID,
    "namespace": settings.WEB_STORE_API_NAMESPACE,
    "userId": "string",
    "status": WebStoreOrderRefundStatus.PAID_ONLINE.value,
    "refundMethod": "string",
    "refundType": "string",
    "refundGateway": "string",
    "totalExclTax": DEFAULT_ITEM["rowPriceNet"],
    "total": DEFAULT_ITEM["rowPriceTotal"],
    "taxAmount": DEFAULT_ITEM["rowPriceVat"],
    "refundTransactionId": "string",
    "timestamp": "string",
}

DEFAULT_GET_REFUND_DATA = {
    "refunds": [
        {
            "refundId": DEFAULT_REFUND_ID,
            "namespace": settings.WEB_STORE_API_NAMESPACE,
            "user": "string",
            "createdAt": "2024-02-02T12:00:00Z",
            "status": WebStoreOrderRefundStatus.PAID_ONLINE.value,
            "customerFirstName": "string",
            "customerLastName": "string",
            "customerEmail": "string",
            "customerPhone": "string",
            "refundReason": "string",
            "items": [DEFAULT_ITEM.copy()],
            "payment": {},
        }
    ]
}
DEFAULT_GET_REFUND_DATA["refunds"][0]["items"][0].update(
    {
        "refundItemId": "string",
        "refundId": "string",
        "originalPriceNet": DEFAULT_ITEM["rowPriceNet"],
        "originalPriceVat": DEFAULT_ITEM["rowPriceVat"],
        "originalPriceGross": DEFAULT_ITEM["rowPriceTotal"],
    }
)
DEFAULT_GET_REFUND_DATA["refunds"][0]["payment"].update(DEFAULT_GET_REFUND_PAYMENT_DATA)


@pytest.mark.parametrize(
    "setting_name,setting_value",
    [
        ("WEB_STORE_API_BASE_URL", None),
        ("WEB_STORE_API_KEY", None),
        ("WEB_STORE_API_NAMESPACE", None),
        ("WEB_STORE_API_BASE_URL", ""),
        ("WEB_STORE_API_KEY", ""),
        ("WEB_STORE_API_NAMESPACE", ""),
    ],
)
def test_mandatory_web_store_payment_setting_missing_causes_right_exception(
    settings, setting_name, setting_value
):
    setattr(settings, setting_name, setting_value)

    with pytest.raises(WebStoreImproperlyConfiguredException):
        WebStorePaymentAPIClient()


def test_get_payment_success():
    client = WebStorePaymentAPIClient()

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{client.payment_api_base_url}admin/{DEFAULT_ORDER_ID}",
            json=DEFAULT_GET_PAYMENT_DATA,
        )

        response_json = client.get_payment(order_id=DEFAULT_ORDER_ID)

        assert req_mock.call_count == 1

    assert response_json == DEFAULT_GET_PAYMENT_DATA


@pytest.mark.parametrize(
    "status_code", [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]
)
def test_get_payment_exception(status_code):
    client = WebStorePaymentAPIClient()

    with requests_mock.Mocker() as req_mock, pytest.raises(RequestException):
        req_mock.get(
            f"{client.payment_api_base_url}admin/{DEFAULT_ORDER_ID}",
            status_code=status_code,
        )

        client.get_payment(order_id=DEFAULT_ORDER_ID)

        assert req_mock.call_count == 1


def test_get_refund_payment_success():
    client = WebStorePaymentAPIClient()

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"{client.payment_api_base_url}admin/refund-payment/{DEFAULT_ORDER_ID}",
            json=DEFAULT_GET_REFUND_PAYMENT_DATA,
        )
        response_json = client.get_refund_payment(order_id=DEFAULT_ORDER_ID)

    assert response_json == DEFAULT_GET_REFUND_PAYMENT_DATA


@pytest.mark.parametrize(
    "status_code", [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]
)
def test_get_refund_payment_exception(status_code):
    client = WebStorePaymentAPIClient()

    with requests_mock.Mocker() as req_mock, pytest.raises(RequestException):
        req_mock.get(
            f"{client.payment_api_base_url}admin/refund-payment/{DEFAULT_ORDER_ID}",
            status_code=status_code,
        )

        client.get_refund_payment(order_id=DEFAULT_ORDER_ID)

        assert req_mock.call_count == 1
