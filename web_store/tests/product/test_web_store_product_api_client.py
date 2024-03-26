from unittest.mock import patch

import pytest
from django.conf import settings as django_settings
from requests import RequestException
from rest_framework import status

from web_store.exceptions import WebStoreImproperlyConfiguredException
from web_store.product.clients import WebStoreProductAPIClient
from web_store.tests.utils import get_mock_response

DEFAULT_PRODUCT_ID = "5aa48bcf-91a3-4c79-87e5-232f4006c5f2"

DEFAULT_CREATE_PRODUCT_MAPPING_DATA = {
    "namespace": django_settings.WEB_STORE_API_NAMESPACE,
    "namespaceEntityId": "string",
    "merchantId": "string",
}

DEFAULT_GET_PRODUCT_MAPPING_DATA = {
    "productMapping": {
        "namespace": django_settings.WEB_STORE_API_NAMESPACE,
        "namespaceEntityId": "string",
        "merchantId": "string",
        "productId": DEFAULT_PRODUCT_ID,
    }
}

DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA = {
    "vatCode": "string",
    "internalOrder": "string",
    "profitCenter": "string",
    "balanceProfitCenter": "string",
    "project": "string",
    "operationArea": "string",
    "companyCode": "string",
    "mainLedgerAccount": "string",
    "productInvoicing": {
        "salesOrg": "string",
        "salesOffice": "string",
        "material": "string",
        "orderType": "string",
    },
}

DEFAULT_GET_PRODUCT_ACCOUNTING_DATA = DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA.copy()
DEFAULT_GET_PRODUCT_ACCOUNTING_DATA.update(
    {
        "productId": DEFAULT_PRODUCT_ID,
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
def test_product_api_mandatory_web_store_order_setting_missing_causes_right_exception(
    settings, setting_name, setting_value
):
    setattr(settings, setting_name, setting_value)

    with pytest.raises(WebStoreImproperlyConfiguredException):
        WebStoreProductAPIClient()


def test_create_product_mapping_success():
    client = WebStoreProductAPIClient()
    mocked_response = get_mock_response(
        json_return_value=DEFAULT_GET_PRODUCT_MAPPING_DATA
    )

    with patch("requests.post") as mocked_request:
        mocked_request.return_value = mocked_response
        response_json = client.create_product_mapping(
            DEFAULT_CREATE_PRODUCT_MAPPING_DATA
        )

    assert response_json == DEFAULT_GET_PRODUCT_MAPPING_DATA


@pytest.mark.parametrize(
    "status_code", [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]
)
def test_create_product_mapping_exception(status_code):
    client = WebStoreProductAPIClient()
    mocked_response = get_mock_response(status_code=status_code)

    with patch("requests.post") as mocked_request, pytest.raises(RequestException):
        mocked_request.return_value = mocked_response
        client.create_product_mapping(DEFAULT_CREATE_PRODUCT_MAPPING_DATA)


def test_create_product_accounting_success():
    client = WebStoreProductAPIClient()
    mocked_response = get_mock_response(
        json_return_value=DEFAULT_GET_PRODUCT_ACCOUNTING_DATA
    )

    with patch("requests.post") as mocked_request:
        mocked_request.return_value = mocked_response
        response_json = client.create_product_accounting(
            DEFAULT_PRODUCT_ID, DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA
        )

    assert response_json == DEFAULT_GET_PRODUCT_ACCOUNTING_DATA


@pytest.mark.parametrize(
    "status_code", [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]
)
def test_create_product_accounting_exception(status_code):
    client = WebStoreProductAPIClient()
    mocked_response = get_mock_response(status_code=status_code)

    with patch("requests.post") as mocked_request, pytest.raises(RequestException):
        mocked_request.return_value = mocked_response
        client.create_product_accounting(
            DEFAULT_PRODUCT_ID, DEFAULT_CREATE_PRODUCT_ACCOUNTING_DATA
        )
