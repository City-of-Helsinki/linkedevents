from urllib.parse import parse_qs, urlencode

import pytest
import requests_mock
from requests.exceptions import RequestException
from rest_framework import status

from web_store.clients import WebStoreAPIBaseClient
from web_store.exceptions import WebStoreImproperlyConfiguredException

DEFAULT_API_URL = "https://test_api/v1/"
DEFAULT_HEADERS = {
    "Authorization": "secret",
}
DEFAULT_PARAMS = {
    "key": "value",
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
def test_mandatory_web_store_setting_missing_causes_right_exception(
    settings, setting_name, setting_value
):
    setattr(settings, setting_name, setting_value)

    with pytest.raises(WebStoreImproperlyConfiguredException):
        WebStoreAPIBaseClient()


@pytest.mark.parametrize(
    "api_base_url",
    [
        "https://test-api.dev/",
        "https://test-api.dev",
    ],
)
def test_api_base_url_with_and_without_slash(settings, api_base_url):
    settings.WEB_STORE_API_BASE_URL = api_base_url

    client = WebStoreAPIBaseClient()
    assert client.api_base_url == "https://test-api.dev"


@pytest.mark.parametrize("http_method", ["get", "post", "put", "patch", "delete"])
def test_make_successful_request_with_different_http_methods(http_method):
    client = WebStoreAPIBaseClient()

    with requests_mock.Mocker() as req_mock:
        getattr(req_mock, http_method)(DEFAULT_API_URL, json={})

        resp_json = client._make_request(DEFAULT_API_URL, http_method)

        assert req_mock.call_count == 1

        req_history = req_mock.request_history[0]
        assert req_history.url == DEFAULT_API_URL
        assert req_history.timeout == client.TIMEOUT

    assert isinstance(resp_json, dict)


@pytest.mark.parametrize(
    "http_method,params_key,params_value",
    [
        ("get", "params", DEFAULT_PARAMS),
        ("post", "json", DEFAULT_PARAMS),
        ("put", "json", DEFAULT_PARAMS),
        ("patch", "json", DEFAULT_PARAMS),
        ("delete", "json", DEFAULT_PARAMS),
    ],
)
def test_make_successful_request_with_params(http_method, params_key, params_value):
    client = WebStoreAPIBaseClient()

    with requests_mock.Mocker() as req_mock:
        getattr(req_mock, http_method)(DEFAULT_API_URL, json={})

        resp_json = client._make_request(
            DEFAULT_API_URL, http_method, params=params_value
        )

        assert req_mock.call_count == 1

        req_history = req_mock.request_history[0]
        assert req_history.timeout == client.TIMEOUT
        if params_key == "params":
            assert req_history.url.startswith(DEFAULT_API_URL) is True
            assert req_history.qs == parse_qs(urlencode(params_value))
        else:
            assert req_history.url == DEFAULT_API_URL
            assert req_history.json() == params_value

    assert isinstance(resp_json, dict)


@pytest.mark.parametrize(
    "http_method,headers",
    [
        ("get", DEFAULT_HEADERS),
        ("post", DEFAULT_HEADERS),
        ("put", DEFAULT_HEADERS),
        ("patch", DEFAULT_HEADERS),
        ("delete", DEFAULT_HEADERS),
    ],
)
def test_make_successful_request_with_headers(http_method, headers):
    client = WebStoreAPIBaseClient()

    with requests_mock.Mocker() as req_mock:
        getattr(req_mock, http_method)(DEFAULT_API_URL, json={})

        resp_json = client._make_request(DEFAULT_API_URL, http_method, headers=headers)

        assert req_mock.call_count == 1

        req_history = req_mock.request_history[0]
        assert req_history.timeout == client.TIMEOUT
        assert req_history.url == DEFAULT_API_URL
        assert headers.items() <= req_history.headers.items()

    assert isinstance(resp_json, dict)


@pytest.mark.parametrize(
    "http_method,status_code",
    [
        ("get", status.HTTP_400_BAD_REQUEST),
        ("get", status.HTTP_500_INTERNAL_SERVER_ERROR),
        ("post", status.HTTP_400_BAD_REQUEST),
        ("post", status.HTTP_500_INTERNAL_SERVER_ERROR),
        ("put", status.HTTP_400_BAD_REQUEST),
        ("put", status.HTTP_500_INTERNAL_SERVER_ERROR),
        ("patch", status.HTTP_400_BAD_REQUEST),
        ("patch", status.HTTP_500_INTERNAL_SERVER_ERROR),
        ("delete", status.HTTP_400_BAD_REQUEST),
        ("delete", status.HTTP_500_INTERNAL_SERVER_ERROR),
    ],
)
def test_make_failed_request(http_method, status_code):
    client = WebStoreAPIBaseClient()

    with (
        requests_mock.Mocker() as req_mock,
        pytest.raises(RequestException),
    ):
        getattr(req_mock, http_method)(DEFAULT_API_URL, status_code=status_code)

        client._make_request(DEFAULT_API_URL, http_method)

        assert req_mock.call_count == 1
