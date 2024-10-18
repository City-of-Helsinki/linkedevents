from drf_spectacular.plumbing import ResolvedComponent, get_lib_doc_excludes
from drf_spectacular.settings import spectacular_settings
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, OpenApiTypes


def swagger_endpoint_filter(endpoints) -> list:
    """
    Ensure that only the wanted Linked Events API endpoints are included in the Swagger schema.
    """
    filtered = []

    for path, path_regex, method, callback in endpoints:
        if path.startswith("/{version}/"):
            filtered.append((path, path_regex, method, callback))

    return filtered


def swagger_postprocessing_hook(result, generator, request, public):
    """Among other things, allows to add additional components to the Swagger schema."""
    meta_schema = {
        "type": "object",
        "properties": {
            "meta": {
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                    },
                    "next": {
                        "type": "string",
                        "nullable": True,
                        "format": "uri",
                    },
                    "previous": {
                        "type": "string",
                        "nullable": True,
                        "format": "uri",
                    },
                },
            },
        },
        "description": (
            "Meta record for result pagination. All results from API are paginated, ie. "
            "delivered in chunks of X results. This records describes how many results there "
            "are in total, and how to access previous and next pages."
        ),
    }
    component = ResolvedComponent(
        name="Meta",
        type=ResolvedComponent.SCHEMA,
        schema=meta_schema,
        object="Meta",
    )
    generator.registry.register_on_missing(component)

    # Sort again with additional components.
    result["components"] = generator.registry.build(
        spectacular_settings.APPEND_COMPONENTS
    )

    return result


def swagger_get_lib_doc_excludes() -> list:
    """Exclude unwanted docstrings from the Swagger schema."""
    from rest_framework_bulk import generics

    lib_doc_excludes = get_lib_doc_excludes()

    lib_doc_excludes.extend(
        [
            generics.BulkModelViewSet,
            *[
                getattr(generics, view_class)
                for view_class in dir(generics)
                if view_class.endswith("APIView")
            ],
        ]
    )

    return lib_doc_excludes


def get_common_api_error_responses(excluded_codes=None):
    excluded_codes = excluded_codes or []
    responses = {}

    if 400 not in excluded_codes:
        responses[400] = OpenApiResponse(
            description=(
                "Input format was not correct, eg. mandatory field was missing or "
                "JSON was malformed."
            )
        )

    if 401 not in excluded_codes:
        responses[401] = OpenApiResponse(
            description="User was not authenticated.",
        )

    if 403 not in excluded_codes:
        responses[403] = OpenApiResponse(
            description="User does not have necessary permissions.",
        )

    return responses


def get_custom_data_schema():
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                },
                "value": {
                    "type": "string",
                },
            },
        },
        "description": "Key value field for custom data",
    }


class IncludeOpenApiParameter(OpenApiParameter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("name", "include")
        kwargs.setdefault("type", OpenApiTypes.STR)
        kwargs.setdefault(
            "description",
            (
                "Embed given reference-type fields, comma-separated if several, directly into "
                "the response, otherwise they are returned as URI references."
            ),
        )

        super().__init__(*args, **kwargs)
