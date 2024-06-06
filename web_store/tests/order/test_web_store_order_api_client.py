from unittest.mock import patch

import pytest
import requests_mock
from django.conf import settings as django_settings
from requests.exceptions import RequestException
from rest_framework import status

from web_store.exceptions import WebStoreImproperlyConfiguredException
from web_store.order.clients import WebStoreOrderAPIClient
from web_store.order.enums import WebStoreOrderStatus
from web_store.tests.utils import get_mock_response

DEFAULT_USER_UUID = "f5e87f5c-8d16-4746-8e96-5a5a88b9224e"
DEFAULT_ORDER_ID = "c7ae2960-8284-4b92-b82e-9da882c452d7"
DEFAULT_REFUND_ID = "f99166f6-6bca-4161-970e-79eb96b345a8"
DEFAULT_ITEM = {
    "productId": "product_id",
    "productName": "description",
    "quantity": 1,
    "unit": "pcs",
    "rowPriceNet": "80.65",
    "rowPriceVat": "19.35",
    "rowPriceTotal": "100",
    "priceNet": "80.65",
    "priceGross": "100",
    "priceVat": "19.35",
    "vatPercentage": "24.00",
}

DEFAULT_CREATE_ORDER_DATA = {
    "namespace": django_settings.WEB_STORE_API_NAMESPACE,
    "user": "user_uuid",
    "items": [DEFAULT_ITEM.copy()],
    "priceNet": "0.00",
    "priceVat": "0.00",
    "priceTotal": "0.00",
    "customer": {
        "firstName": "first_name",
        "lastLame": "last_name",
        "email": "test@test.com",
    },
}

DEFAULT_GET_ORDER_DATA = {
    "orderId": DEFAULT_ORDER_ID,
    "createdAt": "2024-02-01T12:00:00Z",
    "checkoutUrl": "https://test.dev/",
    "receiptUrl": "https://test.dev/receipt/",
    "loggedInCheckoutUrl": "https://test.dev/logged_in/",
    "updateCardUrl": "https://test.dev/cart/update/",
    "isValidForCheckout": True,
    "invoice": {
        "invoiceId": "string",
        "businessId": "string",
        "name": "string",
        "address": "string",
        "postcode": "string",
        "city": "string",
        "ovtId": "string",
    },
    "status": WebStoreOrderStatus.DRAFT.value,
    "subscriptionId": "string",
    "type": "subscription",
    "paymentMethod": {
        "name": "string",
        "code": "string",
        "group": "string",
        "img": "string",
        "gateway": "string",
    },
    "merchant": {
        "merchantName": "string",
        "merchantStreet": "string",
        "merchantZip": "string",
        "merchantCity": "string",
        "merchantEmail": "string",
        "merchantUrl": "string",
        "merchantTermsOfServiceUrl": "string",
        "merchantBusinessId": "string",
        "merchantPhone": "string",
        "merchantShopId": "string",
    },
}
DEFAULT_GET_ORDER_DATA.update(DEFAULT_CREATE_ORDER_DATA)

DEFAULT_CANCEL_ORDER_DATA = {
    "order": DEFAULT_GET_ORDER_DATA.copy(),
    "cancelUrl": f"https://test.dev/order/{DEFAULT_ORDER_ID}/cancel",
}

DEFAULT_CREATE_INSTANT_REFUNDS_DATA = [
    {"orderId": DEFAULT_ORDER_ID, "items": [{"orderItemId": "string", "quantity": 1}]}
]

DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE = {
    "refunds": [
        {
            "refundId": DEFAULT_REFUND_ID,
            "orderId": DEFAULT_ORDER_ID,
            "namespace": django_settings.WEB_STORE_API_NAMESPACE,
            "user": "string",
            "createdAt": "2024-02-01T12:00:00Z",
            "status": "draft",
            "customerFirstName": "string",
            "customerLastName": "string",
            "customerEmail": "string",
            "customerPhone": "string",
            "refundReason": "string",
            "items": [
                {
                    "refundItemId": "string",
                    "refundId": "string",
                    "orderItemId": "string",
                    "orderId": "string",
                    "productLabel": "string",
                    "productDescription": "string",
                    "originalPriceNet": "string",
                    "originalPriceVat": "string",
                    "originalPriceGross": "string",
                }
            ],
            "payment": {
                "refundPaymentId": "string",
                "orderId": "string",
                "userId": "string",
                "status": "string",
                "refundMethod": "string",
                "refundType": "string",
                "refundGateway": "string",
                "totalExclTax": 0,
                "total": 0,
                "taxAmount": 0,
                "refundTransactionId": "string",
            },
        }
    ],
}
DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE["refunds"][0]["items"][0].update(DEFAULT_ITEM)


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
def test_mandatory_web_store_order_setting_missing_causes_right_exception(
    settings, setting_name, setting_value
):
    setattr(settings, setting_name, setting_value)

    with pytest.raises(WebStoreImproperlyConfiguredException):
        WebStoreOrderAPIClient()


def test_create_order_success():
    client = WebStoreOrderAPIClient()
    mocked_response = get_mock_response(json_return_value=DEFAULT_CREATE_ORDER_DATA)

    with patch("requests.post") as mocked_request:
        mocked_request.return_value = mocked_response
        response_json = client.create_order(DEFAULT_CREATE_ORDER_DATA)

    assert response_json == DEFAULT_CREATE_ORDER_DATA


@pytest.mark.parametrize(
    "status_code", [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]
)
def test_create_order_exception(status_code):
    client = WebStoreOrderAPIClient()
    mocked_response = get_mock_response(status_code=status_code)

    with patch("requests.post") as mocked_request, pytest.raises(RequestException):
        mocked_request.return_value = mocked_response
        client.create_order(DEFAULT_CREATE_ORDER_DATA)


def test_get_order_success():
    client = WebStoreOrderAPIClient()
    mocked_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=DEFAULT_GET_ORDER_DATA
    )

    with patch("requests.get") as mocked_request:
        mocked_request.return_value = mocked_response
        response_json = client.get_order(order_id=DEFAULT_ORDER_ID)

    assert response_json == DEFAULT_GET_ORDER_DATA


@pytest.mark.parametrize(
    "status_code",
    [
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
)
def test_get_order_exception(status_code):
    client = WebStoreOrderAPIClient()
    mocked_response = get_mock_response(status_code=status_code)

    with patch("requests.get") as mocked_request, pytest.raises(RequestException):
        mocked_request.return_value = mocked_response
        client.get_order(order_id=DEFAULT_ORDER_ID)


def test_cancel_order_success():
    client = WebStoreOrderAPIClient()
    mocked_response = get_mock_response(
        status_code=status.HTTP_200_OK, json_return_value=DEFAULT_CANCEL_ORDER_DATA
    )

    with patch("requests.post") as mocked_request:
        mocked_request.return_value = mocked_response
        response_json = client.cancel_order(
            order_id=DEFAULT_ORDER_ID, user_uuid=DEFAULT_USER_UUID
        )

        assert response_json == DEFAULT_CANCEL_ORDER_DATA


@pytest.mark.parametrize(
    "status_code",
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
)
def test_cancel_order_exception(status_code):
    client = WebStoreOrderAPIClient()
    mocked_response = get_mock_response(status_code=status_code)

    with patch("requests.post") as mocked_request, pytest.raises(RequestException):
        mocked_request.return_value = mocked_response
        client.cancel_order(order_id=DEFAULT_ORDER_ID, user_uuid=DEFAULT_USER_UUID)


def test_create_instant_refunds_success():
    client = WebStoreOrderAPIClient()

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{client.order_api_base_url}refund/instant",
            status_code=status.HTTP_200_OK,
            json=DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE,
        )

        response_json = client.create_instant_refunds(
            DEFAULT_CREATE_INSTANT_REFUNDS_DATA
        )
        assert response_json == DEFAULT_CREATE_INSTANT_REFUNDS_RESPONSE


@pytest.mark.parametrize(
    "status_code",
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
)
def test_create_instant_refunds_exception(status_code):
    client = WebStoreOrderAPIClient()

    with requests_mock.Mocker() as req_mock, pytest.raises(RequestException):
        req_mock.post(
            f"{client.order_api_base_url}refund/instant",
            status_code=status_code,
        )

        client.create_instant_refunds(DEFAULT_CREATE_INSTANT_REFUNDS_DATA)
