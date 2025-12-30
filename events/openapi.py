"""Shared OpenAPI definitions for events API endpoints."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, inline_serializer
from rest_framework import serializers

# Common pagination parameters
# Note: These are generally handled automatically by DRF pagination classes,
# but can be explicitly referenced if needed
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

# Common include parameter is already defined in linkedevents.schema_utils
# as IncludeOpenApiParameter, so we import from there when needed

# Common response structures
STATUS_RESPONSE = inline_serializer(
    name="StatusResponse",
    fields={"status": serializers.CharField()},
)

ERROR_RESPONSE = inline_serializer(
    name="ErrorResponse",
    fields={
        "detail": serializers.CharField(),
    },
)

# Sorting/ordering parameter (common across many endpoints)
SORT_PARAM = OpenApiParameter(
    "sort",
    OpenApiTypes.STR,
    description=(
        "Sort the returned results in the given order. Prefix with '-' for "
        "descending order."
    ),
)
