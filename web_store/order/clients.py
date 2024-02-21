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

    def get_order(self, order_id: str) -> dict:
        return self._make_request(
            f"{self.order_api_base_url}admin/{order_id}",
            "get",
            headers={
                "api-key": self.api_key,
                "namespace": self.api_namespace,
            },
        )

    def cancel_order(self, order_id: str) -> dict:
        return self._make_request(
            f"{self.order_api_base_url}/{order_id}/cancel",
            "post",
            headers={"api-key": self.api_key},
        )
