"""
Django base settings for linkedevents project.
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

DEBUG = False

TEMPLATE_DEBUG = False

ALLOWED_HOSTS = []

SITE_ID = 1

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'timestamped_named': {
            'format': '%(asctime)s %(name)s %(levelname)s: %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'timestamped_named',
        },
        # Just for reference, not used
        'blackhole': {
            'class': 'logging.NullHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
        },
        # Special configuration for elasticsearch, as INFO level prints
        # out every single call to elasticsearch
        'elasticsearch': {
            'level': 'WARNING',
        },
    }
}

# Application definition
INSTALLED_APPS = [
    'helusers',
    'django.contrib.sites',
    'modeltranslation',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django.contrib.postgres',
    'django_extensions',
    'events',
    'corsheaders',
    'rest_framework',
    'rest_framework_gis', 
    'rest_framework_jwt',
    'mptt',
    'reversion',
    'haystack',
    'raven.contrib.django.raven_compat',
    'django_cleanup',
    'django_filters',

    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'helusers.providers.helsinki',

    'helevents',
    'munigeo',
    'leaflet',
    'django_orghierarchy',
]

MIDDLEWARE_CLASSES = [
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'reversion.middleware.RevisionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'linkedevents.urls'

WSGI_APPLICATION = 'linkedevents.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'linkedevents',
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGES = (
    ('fi', 'Finnish'),
    ('sv', 'Swedish'),
    ('en', 'English'),
    ('zh-hans', 'Simplified Chinese'),
    ('ru', 'Russian'),
    ('ar', 'Arabic'),
)

LANGUAGE_CODE = 'fi'

TIME_ZONE = 'Europe/Helsinki'

MUNIGEO_COUNTRY = 'country:fi'
MUNIGEO_MUNI = 'kunta:helsinki'

SYSTEM_DATA_SOURCE_ID = 'system'


USE_I18N = True
USE_L10N = True
USE_TZ = True

LOCALE_PATHS = (
    os.path.join(BASE_DIR, 'locale'),
)

IMPORT_FILE_PATH = os.path.join(BASE_DIR, 'data')

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

#
# Authentication
#
AUTH_USER_MODEL = 'helevents.User'
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)
SOCIALACCOUNT_PROVIDERS = {
    'helsinki': {
        'VERIFIED_EMAIL': True
    }
}
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_ON_GET = True
SOCIALACCOUNT_ADAPTER = 'helusers.adapter.SocialAccountAdapter'

#
# REST Framework
#
REST_FRAMEWORK = {
    'PAGE_SIZE': 20,
    'ORDERING_PARAM': 'sort',
    'DEFAULT_RENDERER_CLASSES': (
        'events.renderers.JSONRenderer',
        'events.renderers.JSONLDRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'events.parsers.CamelCaseJSONParser',
        'events.parsers.JSONLDParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
    'DEFAULT_PAGINATION_CLASS': 'events.api_pagination.CustomPagination',
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'events.auth.ApiKeyAuthentication',
        'helusers.jwt.JWTAuthentication',
    ),
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'VIEW_NAME_FUNCTION': 'events.api.get_view_name',
}
JWT_AUTH = {
    'JWT_PAYLOAD_GET_USER_ID_HANDLER': 'helusers.jwt.get_user_id_from_payload_handler',
    # JWT_AUDIENCE and JWT_SECRET_KEY must be set in local_settings.py
}


CORS_ORIGIN_ALLOW_ALL = True
CSRF_COOKIE_NAME = 'linkedevents-csrftoken'
SESSION_COOKIE_NAME = 'linkedevents-sessionid'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


POSTGIS_VERSION = (2, 1, 1)

# Use ETRS-TM35FIN projection by default
PROJECTION_SRID = 3067
# Bounding box of Finland and then some

BOUNDING_BOX = [-548576, 6291456, 1548576, 8388608]

CITYSDK_API_SETTINGS = {
    'CITYSDK_URL': "http://api.tourism.helsinki.citysdk.eu/CitySDK/",
    'USERNAME': 'admin',
    'PASSWORD': 'defaultCitySDKPassword',
    'SRS_URL': 'http://www.opengis.net/def/crs/EPSG/0/%d' % PROJECTION_SRID,
    'DEFAULT_POI_CATEGORY': '53562f3238653c0a842a3bf7'
}

HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.RealtimeSignalProcessor'

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'multilingual_haystack.backends.MultilingualSearchEngine'
    },
    'default-fi': {
        'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
        'BASE_ENGINE': 'haystack.backends.simple_backend.SimpleEngine'
    },
    'default-en': {
        'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
        'BASE_ENGINE': 'haystack.backends.simple_backend.SimpleEngine'
    },
    'default-sv': {
        'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
        'BASE_ENGINE': 'haystack.backends.simple_backend.SimpleEngine'
    },
    'default-zh-hans': {
        'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
        'BASE_ENGINE': 'haystack.backends.simple_backend.SimpleEngine'
    },
    'default-ru': {
        'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
        'BASE_ENGINE': 'haystack.backends.simple_backend.SimpleEngine'
    },
    'default-ar': {
        'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
        'BASE_ENGINE': 'haystack.backends.simple_backend.SimpleEngine'
    }
}


import bleach  # noqa
BLEACH_ALLOWED_TAGS = bleach.ALLOWED_TAGS + ["p", "div", "br"]

from easy_thumbnails.conf import Settings as thumbnail_settings  # noqa
THUMBNAIL_PROCESSORS = (
    'image_cropping.thumbnail_processors.crop_corners',
) + thumbnail_settings.THUMBNAIL_PROCESSORS


# django-orghierachy swappable model
DJANGO_ORGHIERARCHY_DATASOURCE_MODEL = 'events.DataSource'

AUTO_ENABLED_EXTENSIONS = []

# local_settings.py can be used to override environment-specific settings
# like database and email that differ between development and production.
f = os.path.join(BASE_DIR, "local_settings.py")
if os.path.exists(f):
    import sys
    import imp
    module_name = "%s.local_settings" % ROOT_URLCONF.split('.')[0]
    module = imp.new_module(module_name)
    module.__file__ = f
    sys.modules[module_name] = module
    exec(open(f, "rb").read())

if 'SECRET_KEY' not in locals():
    secret_file = os.path.join(BASE_DIR, '.django_secret')
    try:
        SECRET_KEY = open(secret_file).read().strip()
    except IOError:
        import random
        system_random = random.SystemRandom()
        try:
            SECRET_KEY = ''.join(
                [system_random.choice('abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)')
                 for i in range(64)])
            secret = open(secret_file, 'w')
            import os
            os.chmod(secret_file, 0o0600)
            secret.write(SECRET_KEY)
            secret.close()
        except IOError:
            Exception('Please create a %s file with random characters to generate your secret key!' % secret_file)
