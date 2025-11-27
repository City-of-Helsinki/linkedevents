from typing import Any

import requests
from django.conf import settings

from web_store.exceptions import WebStoreImproperlyConfiguredError


class WebStoreAPIBaseClient:
    TIMEOUT = 30  # seconds

    def __init__(self):
        if not all(
            [
                settings.WEB_STORE_API_BASE_URL,
                settings.WEB_STORE_API_NAMESPACE,
                settings.WEB_STORE_API_KEY,
            ]
        ):
            raise WebStoreImproperlyConfiguredError(
                "One or more mandatory Talpa web store setting is missing. "
                "Please check environment variables with the prefix WEB_STORE_."
            )

        if settings.WEB_STORE_API_BASE_URL.endswith("/"):
            self.api_base_url = settings.WEB_STORE_API_BASE_URL[:-1]
        else:
            self.api_base_url = settings.WEB_STORE_API_BASE_URL
        self.api_namespace = settings.WEB_STORE_API_NAMESPACE
        self.api_key = settings.WEB_STORE_API_KEY

    def _get_request_kwargs(
        self,
        method: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> dict[str, int | dict]:
        request_kwargs = {"timeout": self.TIMEOUT}

        if not (params or headers):
            return request_kwargs

        if params:
            params_key = "params" if method == "get" else "json"
            request_kwargs[params_key] = params

        if headers:
            request_kwargs["headers"] = headers

        return request_kwargs

    def _make_request(
        self,
        url: str,
        method: str,
        params: dict | list | None = None,
        headers: dict | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        request_kwargs = self._get_request_kwargs(method, params, headers)
        response = getattr(requests, method)(url, **request_kwargs)

        response.raise_for_status()

        return response.json()
