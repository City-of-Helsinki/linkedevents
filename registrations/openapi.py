"""Shared OpenAPI definitions for registrations API endpoints."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, inline_serializer
from rest_framework import serializers

# Common pagination parameters
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

# Common response structures
STATUS_RESPONSE = inline_serializer(
    name="RegistrationStatusResponse",
    fields={"status": serializers.CharField()},
)

MESSAGE_SENT_RESPONSE = inline_serializer(
    name="MessageSentResponse",
    fields={
        "message": serializers.CharField(),
        "count": serializers.IntegerField(),
    },
)

# Sorting parameter
SORT_PARAM = OpenApiParameter(
    "sort",
    OpenApiTypes.STR,
    description=(
        "Sort the returned results in the given order. Prefix with '-' for "
        "descending order."
    ),
)
