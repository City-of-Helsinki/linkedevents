from web_store.clients import WebStoreAPIBaseClient


class WebStoreOrderAPIClient(WebStoreAPIBaseClient):
    def __init__(self):
        super().__init__()

        self.order_api_base_url = f"{self.api_base_url}/order/"

    def create_order(self, data: dict) -> dict:
        return self._make_request(
            self.order_api_base_url,
            "post",
            params=data,
            headers={"api-key": self.api_key},
        )
