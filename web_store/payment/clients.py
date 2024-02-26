from web_store.clients import WebStoreAPIBaseClient


class WebStorePaymentAPIClient(WebStoreAPIBaseClient):
    def __init__(self):
        super().__init__()

        self.payment_api_base_url = f"{self.api_base_url}/payment/"

    def get_payment(self, order_id: str) -> dict:
        return self._make_request(
            f"{self.payment_api_base_url}admin/{order_id}",
            "get",
            headers={
                "api-key": self.api_key,
                "namespace": self.api_namespace,
            },
        )

    def create_instant_refund(self, order_id: str) -> dict:
        return self._make_request(
            f"{self.payment_api_base_url}refund/instant/{order_id}",
            "get",
            headers={
                "api-key": self.api_key,
            },
        )
