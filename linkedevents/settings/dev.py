"""Development server settings and globals."""

from base import *

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

# Local overrides
try:
    from local_settings import *
except ImportError:
    pass