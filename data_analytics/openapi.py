"""Shared OpenAPI definitions for data analytics API endpoints."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

# Common pagination parameters for data analytics endpoints
PAGINATION_PARAMS = [
    OpenApiParameter(
        "limit",
        OpenApiTypes.INT,
        description="Number of results to return per page",
    ),
    OpenApiParameter(
        "offset",
        OpenApiTypes.INT,
        description="The initial index from which to return the results",
    ),
]
