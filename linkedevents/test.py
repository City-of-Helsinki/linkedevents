import logging
import environ

# Load main setting
from .settings import *  # noqa: F401, F403

logger = logging.getLogger(__name__)

logger.info("LOADING TEST MODULE SETTINGS")

env = environ.Env(
    DATABASE_URL=(str, 'postgis://postgres:secret@localhost/linkedevents'),
)

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

DATABASES = {
    'default': env.db()
}


def dummy_haystack_connection_without_warnings_for_lang(language_code):
    return {f'default-{language_code}': {
                'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
                'BASE_ENGINE': 'multilingual_haystack.backends.SimpleEngineWithoutWarnings'
                }
            }


for language in [l[0] for l in LANGUAGES]:  # noqa: F405
    connection = dummy_haystack_connection_without_warnings_for_lang(language)
    HAYSTACK_CONNECTIONS.update(connection)  # noqa: F405
