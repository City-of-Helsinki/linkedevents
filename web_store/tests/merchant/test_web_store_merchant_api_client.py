from unittest.mock import patch

import pytest
from requests import RequestException
from rest_framework import status

from web_store.exceptions import WebStoreImproperlyConfiguredException
from web_store.merchant.clients import WebStoreMerchantAPIClient
from web_store.tests.utils import get_mock_response

DEFAULT_CREATE_UPDATE_MERCHANT_DATA = {
    "merchantName": "string",
    "merchantStreet": "string",
    "merchantZip": "string",
    "merchantCity": "string",
    "merchantEmail": "string",
    "merchantPhone": "string",
    "merchantUrl": "string",
    "merchantTermsOfServiceUrl": "string",
    "merchantBusinessId": "string",
    "merchantPaytrailMerchantId": "string",
}

DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA = {
    "merchantId": "string",
    "namespace": "string",
    "createdAt": "string",
    "updatedAt": "string",
    "configurations": [
        {
            "key": "string",
            "value": "string",
            "restricted": True,
        },
    ],
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
def test_merchant_client_mandatory_setting_missing_causes_right_exception(
    settings, setting_name, setting_value
):
    setattr(settings, setting_name, setting_value)

    with pytest.raises(WebStoreImproperlyConfiguredException):
        WebStoreMerchantAPIClient()


def test_create_merchant_success():
    client = WebStoreMerchantAPIClient()
    mocked_response = get_mock_response(
        json_return_value=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA
    )

    with patch("requests.post") as mocked_request:
        mocked_request.return_value = mocked_response
        response_json = client.create_merchant(DEFAULT_CREATE_UPDATE_MERCHANT_DATA)

    assert response_json == DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA


@pytest.mark.parametrize(
    "status_code",
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
)
def test_create_merchant_exception(status_code):
    client = WebStoreMerchantAPIClient()
    mocked_response = get_mock_response(status_code=status_code)

    with patch("requests.post") as mocked_request, pytest.raises(RequestException):
        mocked_request.return_value = mocked_response
        client.create_merchant(DEFAULT_CREATE_UPDATE_MERCHANT_DATA)


def test_update_merchant_success():
    client = WebStoreMerchantAPIClient()
    mocked_response = get_mock_response(
        status_code=status.HTTP_200_OK,
        json_return_value=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
    )

    with patch("requests.post") as mocked_request:
        mocked_request.return_value = mocked_response
        response_json = client.update_merchant(
            "1234", DEFAULT_CREATE_UPDATE_MERCHANT_DATA
        )

    assert response_json == DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA


@pytest.mark.parametrize(
    "status_code",
    [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ],
)
def test_update_merchant_exception(status_code):
    client = WebStoreMerchantAPIClient()
    mocked_response = get_mock_response(status_code=status_code)

    with patch("requests.post") as mocked_request, pytest.raises(RequestException):
        mocked_request.return_value = mocked_response
        client.update_merchant("1234", DEFAULT_CREATE_UPDATE_MERCHANT_DATA)
