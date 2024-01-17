from django.conf import settings
from rest_framework.routers import APIRootView
from rest_framework.views import get_view_name as original_get_view_name


def get_view_name(view):
    if type(view) is APIRootView:
        return getattr(settings, "INSTANCE_NAME", "Linked Events")
    return original_get_view_name(view)


def get_fixed_lang_codes():
    lang_codes = []

    for language in settings.LANGUAGES:
        lang_code = language[0]
        lang_code = lang_code.replace(
            "-", "_"
        )  # to handle complex codes like e.g. zh-hans
        lang_codes.append(lang_code)

    return lang_codes
