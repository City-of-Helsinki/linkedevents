from django.conf import settings
from rest_framework import serializers


def get_view_name(view):
    from rest_framework.routers import APIRootView
    from rest_framework.views import get_view_name as original_get_view_name

    if type(view) is APIRootView:
        return getattr(settings, "INSTANCE_NAME", "Linked Events")
    return original_get_view_name(view)


def get_fixed_lang_codes() -> list[str]:
    """
    Returns a list of language codes.
    Replaces "-" with "_" in the language codes.
    :return: a list of language codes
    """
    return [lang_code[0].replace("-", "_") for lang_code in settings.LANGUAGES]


def validate_serializer_field_for_duplicates(values, field, error_detail_callback):
    errors = []
    checked_values = set()
    raise_errors = False

    for data in values:
        value = data[field]
        if value in checked_values:
            errors.append({field: [error_detail_callback(value)]})
            raise_errors = True
        else:
            checked_values.add(value)
            errors.append({})

    if raise_errors:
        raise serializers.ValidationError(errors)

    return values
