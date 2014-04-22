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

CITYSDK_API_SETTINGS = {
    'CITYSDK_URL': "http://5.9.148.236/CitySDK/",
    'USERNAME': 'admin',
    'PASSWORD': 'defaultCitySDKPassword',
    'SRS_URL': 'http://www.opengis.net/def/crs/EPSG/0/%d' % PROJECTION_SRID,
    'DEFAULT_POI_CATEGORY': '5356093338653c08ace01cf3'
}

# local_settings.py can be used to override environment-specific settings
# like database and email that differ between development and production.
try:
    from local_settings import *
except ImportError:
    pass