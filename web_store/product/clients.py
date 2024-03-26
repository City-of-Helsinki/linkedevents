from web_store.clients import WebStoreAPIBaseClient


class WebStoreProductAPIClient(WebStoreAPIBaseClient):
    def __init__(self):
        super().__init__()

        self.product_api_base_url = f"{self.api_base_url}/product/"

    def create_product_mapping(self, data: dict) -> dict:
        return self._make_request(
            f"{self.product_api_base_url}",
            "post",
            params=data,
            headers={
                "api-key": self.api_key,
            },
        )

    def create_product_accounting(self, product_id: str, data: dict) -> dict:
        return self._make_request(
            f"{self.product_api_base_url}{product_id}/accounting",
            "post",
            params=data,
            headers={
                "api-key": self.api_key,
                "namespace": self.api_namespace,
            },
        )
