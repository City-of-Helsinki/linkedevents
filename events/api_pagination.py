from collections import OrderedDict

from django.utils.translation import gettext_lazy as _
from rest_framework import pagination
from rest_framework.response import Response


# This needs to be in its own file because of circular
# imports.
class CustomPagination(pagination.PageNumberPagination):
    max_page_size = 100

    page_size_query_param = "page_size"
    page_size_query_description = _(
        "Number of results to return per page. %(max_page_size)s is the maximum value for page_size."  # noqa: E501
    ) % {"max_page_size": max_page_size}

    def get_paginated_response(self, data):
        meta = OrderedDict(
            [
                ("count", self.page.paginator.count),
                ("next", self.get_next_link()),
                ("previous", self.get_previous_link()),
            ]
        )

        return Response(OrderedDict([("meta", meta), ("data", data)]))

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "meta": {
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "example": 0,
                        },
                        "next": {
                            "type": "string",
                            "nullable": True,
                            "format": "uri",
                            "example": (
                                f"https://api.url/v1/example-endpoint/?{self.page_query_param}=4"
                            ),
                        },
                        "previous": {
                            "type": "string",
                            "nullable": True,
                            "format": "uri",
                            "example": (
                                f"https://api.url/v1/example-endpoint?{self.page_query_param}=2"
                            ),
                        },
                    },
                },
                "data": schema,
            },
        }


class LargeResultsSetPagination(CustomPagination):
    max_page_size = 1000

    page_size = 1000
    page_size_query_description = _(
        "Number of results to return per page. %(max_page_size)s is the maximum value for page_size."  # noqa: E501
    ) % {"max_page_size": max_page_size}
