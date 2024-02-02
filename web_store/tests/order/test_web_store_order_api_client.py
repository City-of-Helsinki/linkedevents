from decimal import Decimal
from unittest.mock import patch

import pytest
from requests.exceptions import RequestException
from rest_framework import status

from web_store.exceptions import WebStoreImproperlyConfiguredException
from web_store.order.clients import WebStoreOrderAPIClient
from web_store.tests.test_web_store_api_base_client import get_mock_response

DEFAULT_ORDER_DATA = {
    "namespace": "namespace",
    "user": "user_uuid",
    "items": [
        {
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
    ],
    "priceNet": Decimal("0"),
    "priceVat": Decimal("0"),
    "priceTotal": Decimal("0"),
    "customer": {
        "firstName": "first_name",
        "lastLame": "last_name",
        "email": "test@test.com",
    },
}


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
    mocked_response = get_mock_response(json_return_value=DEFAULT_ORDER_DATA)

    with patch("requests.post") as mocked_request:
        mocked_request.return_value = mocked_response
        response_json = client.create_order(DEFAULT_ORDER_DATA)

    assert response_json == DEFAULT_ORDER_DATA


@pytest.mark.parametrize(
    "status_code", [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]
)
def test_create_order_exception(status_code):
    client = WebStoreOrderAPIClient()
    mocked_response = get_mock_response(status_code=status_code)

    with patch("requests.post") as mocked_request, pytest.raises(RequestException):
        mocked_request.return_value = mocked_response
        client.create_order(DEFAULT_ORDER_DATA)
