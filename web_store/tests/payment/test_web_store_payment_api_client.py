from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
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
)
from web_store.tests.utils import get_mock_response

DEFAULT_PAYMENT_ID = str(uuid4())

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

DEFAULT_GET_REFUND_DATA = {
    "refunds": [
        {
            "refundId": "string",
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
            "payment": {
                "refundPaymentId": "string",
                "orderId": "string",
                "userId": "string",
                "status": "string",
                "refundMethod": "string",
                "refundType": "string",
                "refundGateway": "string",
                "totalExclTax": DEFAULT_ITEM["rowPriceNet"],
                "total": DEFAULT_ITEM["rowPriceTotal"],
                "taxAmount": DEFAULT_ITEM["rowPriceVat"],
                "refundTransactionId": "string",
            },
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
    mocked_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=DEFAULT_GET_PAYMENT_DATA
    )

    with patch("requests.get") as mocked_request:
        mocked_request.return_value = mocked_response
        response_json = client.get_payment(order_id=DEFAULT_ORDER_ID)

    assert response_json == DEFAULT_GET_PAYMENT_DATA


@pytest.mark.parametrize(
    "status_code", [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]
)
def test_get_payment_exception(status_code):
    client = WebStorePaymentAPIClient()
    mocked_response = get_mock_response(status_code=status_code)

    with patch("requests.get") as mocked_request, pytest.raises(RequestException):
        mocked_request.return_value = mocked_response
        client.get_payment(order_id=DEFAULT_ORDER_ID)
