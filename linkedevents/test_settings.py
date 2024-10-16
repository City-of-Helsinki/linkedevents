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
OIDC_API_TOKEN_AUTH["ISSUER"] = ["https://test_issuer"]
OIDC_API_TOKEN_AUTH["AUDIENCE"] = ["linkedevents-api-pytest"]
OIDC_API_TOKEN_AUTH["API_AUTHORIZATION_FIELD"] = ["authorization.permissions.scopes"]
GDPR_API_QUERY_SCOPE = "gdprquery"
GDPR_API_DELETE_SCOPE = "gdprdelete"


SECRET_KEY = "xxx"

FIELD_ENCRYPTION_KEYS = (
    "c87a6669a1ded2834f1dfd0830d86ef6cdd20372ac83e8c7c23feffe87e6a051",
)

AUDIT_LOG_ENABLED = True

WEB_STORE_INTEGRATION_ENABLED = True
WEB_STORE_API_BASE_URL = "https://test_api/v1/"
WEB_STORE_API_KEY = "abcd"
WEB_STORE_API_NAMESPACE = "test"
WEB_STORE_WEBHOOK_API_KEY = "1234"
