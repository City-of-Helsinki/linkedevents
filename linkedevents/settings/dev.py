"""Development server settings and globals."""

from .base import *

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'linkedevents',
        'USER': 'linkedevents',
        'PASSWORD': 'linkedevents',
        'HOST': 'localhost',
        'PORT': '',
    }
}

# local_settings.py can be used to override environment-specific settings
# like database and email that differ between development and production.
try:
    from .local_settings import *
except ImportError:
    pass