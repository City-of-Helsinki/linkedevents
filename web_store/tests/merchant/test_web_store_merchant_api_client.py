import pytest
import requests_mock
from requests import RequestException
from rest_framework import status

from web_store.exceptions import WebStoreImproperlyConfiguredException
from web_store.merchant.clients import WebStoreMerchantAPIClient

DEFAULT_MERCHANT_ID = "ec3d83a2-a60c-4a0d-ae5e-55b37d95d059"

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
    "merchantId": DEFAULT_MERCHANT_ID,
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

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{client.merchant_api_base_url}create/merchant/{client.api_namespace}",
            json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
        )

        response_json = client.create_merchant(DEFAULT_CREATE_UPDATE_MERCHANT_DATA)

        assert req_mock.call_count == 1

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

    with requests_mock.Mocker() as req_mock, pytest.raises(RequestException):
        req_mock.post(
            f"{client.merchant_api_base_url}create/merchant/{client.api_namespace}",
            status_code=status_code,
        )

        client.create_merchant(DEFAULT_CREATE_UPDATE_MERCHANT_DATA)

        assert req_mock.call_count == 1


def test_update_merchant_success():
    client = WebStoreMerchantAPIClient()

    with requests_mock.Mocker() as req_mock:
        req_mock.post(
            f"{client.merchant_api_base_url}update/merchant/"
            f"{client.api_namespace}/{DEFAULT_MERCHANT_ID}",
            json=DEFAULT_CREATE_UPDATE_MERCHANT_RESPONSE_DATA,
        )

        response_json = client.update_merchant(
            DEFAULT_MERCHANT_ID, DEFAULT_CREATE_UPDATE_MERCHANT_DATA
        )

        assert req_mock.call_count == 1

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

    with requests_mock.Mocker() as req_mock, pytest.raises(RequestException):
        req_mock.post(
            f"{client.merchant_api_base_url}update/merchant/"
            f"{client.api_namespace}/{DEFAULT_MERCHANT_ID}",
            status_code=status_code,
        )

        client.update_merchant(DEFAULT_MERCHANT_ID, DEFAULT_CREATE_UPDATE_MERCHANT_DATA)

        assert req_mock.call_count == 1
