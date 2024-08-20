from web_store.clients import WebStoreAPIBaseClient


class WebStorePaymentAPIClient(WebStoreAPIBaseClient):
    def __init__(self):
        super().__init__()

        self.payment_api_base_url = f"{self.api_base_url}/payment/"
        self.headers = {
            "api-key": self.api_key,
            "namespace": self.api_namespace,
        }

    def get_payment(self, order_id: str) -> dict:
        return self._make_request(
            f"{self.payment_api_base_url}admin/{order_id}",
            "get",
            headers=self.headers,
        )

    def get_refund_payments(self, refund_id: str) -> list[dict]:
        return self._make_request(
            f"{self.payment_api_base_url}admin/refunds/{refund_id}/payment",
            "get",
            headers=self.headers,
        )
