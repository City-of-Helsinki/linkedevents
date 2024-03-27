from django.conf import settings

from web_store.clients import WebStoreAPIBaseClient


class WebStoreMerchantAPIClient(WebStoreAPIBaseClient):
    def __init__(self):
        super().__init__()

        self.merchant_api_base_url = f"{self.api_base_url}/merchant/"

    def create_merchant(self, data: dict) -> dict:
        return self._make_request(
            f"{self.merchant_api_base_url}create/merchant/{settings.WEB_STORE_API_NAMESPACE}",
            "post",
            params=data,
            headers={"api-key": self.api_key},
        )

    def update_merchant(self, merchant_id: str, data: dict) -> dict:
        return self._make_request(
            f"{self.merchant_api_base_url}update/merchant/"
            f"{settings.WEB_STORE_API_NAMESPACE}/{merchant_id}",
            "post",
            params=data,
            headers={"api-key": self.api_key},
        )
