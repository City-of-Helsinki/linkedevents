# flake8: noqa
"""
Django settings module for pytest
"""
from .settings import *


def dummy_haystack_connection_without_warnings_for_lang(language_code):
    return {
        f"default-{language_code}": {
            "ENGINE": "multilingual_haystack.backends.LanguageSearchEngine",
            "BASE_ENGINE": "multilingual_haystack.backends.SimpleEngineWithoutWarnings",
        }
    }


for language in [lang[0] for lang in LANGUAGES]:
    connection = dummy_haystack_connection_without_warnings_for_lang(language)
    HAYSTACK_CONNECTIONS.update(connection)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}


# Auth
SOCIAL_AUTH_TUNNISTAMO_OIDC_ENDPOINT = "https://test_issuer"
OIDC_API_TOKEN_AUTH["ISSUER"] = "https://test_issuer"

SECRET_KEY = "xxx"

# Enable registration related routes for pytest
ENABLE_REGISTRATION_ENDPOINTS = True
