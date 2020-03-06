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
