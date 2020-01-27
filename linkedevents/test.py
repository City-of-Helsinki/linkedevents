import logging
import environ

# Load main setting
from .settings import *  # noqa: F401, F403

logger = logging.getLogger(__name__)

logger.info("LOADING TEST MODULE SETTINGS")

env = environ.Env(
    DATABASE_URL=(str, 'postgis://linkedevents:linkedevents@localhost/linkedevents'),
)

DATABASES = {
    'default': env.db()
}
