"""
Django settings module for linkedevents project.
"""
import os
import environ
import sentry_sdk
import subprocess
from sentry_sdk.integrations.django import DjangoIntegration
from django.conf.global_settings import LANGUAGES as GLOBAL_LANGUAGES
from django.core.exceptions import ImproperlyConfigured

CONFIG_FILE_NAME = "config_dev.toml"


def get_git_revision_hash() -> str:
    """
    Retrieve the git hash for the underlying git repository or die trying

    We need a way to retrieve git revision hash for sentry reports
    I assume that if we have a git repository available we will
    have git-the-comamand as well
    """
    try:
        # We are not interested in gits complaints
        git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL, encoding='utf8')
    # ie. "git" was not found
    # should we return a more generic meta hash here?
    # like "undefined"?
    except FileNotFoundError:
        git_hash = "git_not_available"
    except subprocess.CalledProcessError:
        # Ditto
        git_hash = "no_repository"
    return git_hash.rstrip()


root = environ.Path(__file__) - 2  # two levels back in hierarchy
env = environ.Env(
    DEBUG=(bool, False),
    SYSTEM_DATA_SOURCE_ID=(str, 'system'),
    LANGUAGES=(list, ['fi', 'sv', 'en', 'zh-hans', 'ru', 'ar']),
    CACHE_URL=(str, 'redis://redis/0'),
    DATABASE_URL=(str, 'postgis:///linkedevents'),
    TOKEN_AUTH_ACCEPTED_AUDIENCE=(str, ''),
    TOKEN_AUTH_SHARED_SECRET=(str, ''),
    ELASTICSEARCH_URL=(str, None),
    SECRET_KEY=(str, ''),
    ALLOWED_HOSTS=(list, []),
    ADMINS=(list, []),
    SECURE_PROXY_SSL_HEADER=(tuple, None),
    USE_X_FORWARDED_HOST=(bool, False),
    CUSTOM_X_FORWARDED_PORT_HEADER=(str, 'LINKEDEVENTS-X-FORWARDED-PORT'),
    CUSTOM_X_FORWARDED_PROTO_HEADER=(str, 'LINKEDEVENTS-X-FORWARDED-PROTO'),
    MEDIA_ROOT=(environ.Path(), root('media')),
    STATIC_ROOT=(environ.Path(), root('static')),
    MEDIA_URL=(str, '/media/'),
    STATIC_URL=(str, '/static/'),
    SENTRY_DSN=(str, ''),
    SENTRY_ENVIRONMENT=(str, 'development'),
    COOKIE_PREFIX=(str, 'linkedevents'),
    INTERNAL_IPS=(list, []),
    INSTANCE_NAME=(str, 'Linked Events'),
    EXTRA_INSTALLED_APPS=(list, []),
    AUTO_ENABLED_EXTENSIONS=(list, []),
    STATICFILES_STORAGE=(str, 'django.contrib.staticfiles.storage.StaticFilesStorage'),
    AWS_STATIC_STORAGE_BUCKET_NAME=(str, ''),
    AWS_STATIC_DEFAULT_ACL=(str, None),
    AWS_STATIC_S3_CUSTOM_DOMAIN=(str, ''),
    DEFAULT_FILE_STORAGE=(str, 'django.core.files.storage.FileSystemStorage'),
    AWS_MEDIA_STORAGE_BUCKET_NAME=(str, ''),
    AWS_MEDIA_DEFAULT_ACL=(str, None),
    AWS_MEDIA_S3_CUSTOM_DOMAIN=(str, ''),
)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = root()

# Django environ has a nasty habit of complanining at level
# WARN about env file not being preset. Here we pre-empt it.
env_file_path = os.path.join(BASE_DIR, CONFIG_FILE_NAME)
if os.path.exists(env_file_path):
    # Logging configuration is not available at this point
    print(f'Reading config from {env_file_path}')
    environ.Env.read_env(env_file_path)

DEBUG = env('DEBUG')
TEMPLATE_DEBUG = False

ALLOWED_HOSTS = env('ALLOWED_HOSTS')
ADMINS = env('ADMINS')
INTERNAL_IPS = env('INTERNAL_IPS',
                   default=(['127.0.0.1'] if DEBUG else []))
DATABASES = {
    'default': env.db()
}

# The default number of seconds to cache a page for the cache middleware.
# See: https://docs.djangoproject.com/en/dev/ref/settings/#cache-middleware-seconds
CACHE_MIDDLEWARE_SECONDS = 60

# A dictionary containing the settings for all caches to be used with Django.
# See: https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    # django-environ doesn't support the rediss:// cache URL scheme needed for TLS connections. That's why we don't use
    # env.cache()
    # See https://github.com/joke2k/django-environ/issues/210
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('CACHE_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Controls where Django stores session data. The django.contrib.sessions.backends.cache setting stores session data
# directly in the cache.
# See: https://docs.djangoproject.com/en/dev/ref/settings/#session-engine
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# Whether a user's session cookie expires when the Web browser is closed.
# See: https://docs.djangoproject.com/en/dev/ref/settings/#session-expire-at-browser-close
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# The age of session cookies, in seconds. Currently, set to 2 hours.
# See: https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-age
SESSION_COOKIE_AGE = 7200

SYSTEM_DATA_SOURCE_ID = env('SYSTEM_DATA_SOURCE_ID')

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
    'rest_framework_jwt',
    'mptt',
    'reversion',
    'haystack',
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

    'storages',
] + env('EXTRA_INSTALLED_APPS')

if not DEBUG:
    # Remove this application from production, so that we don't need to install dev deps there
    INSTALLED_APPS.remove("django_extensions")

if env('SENTRY_DSN'):
    sentry_sdk.init(
        dsn=env('SENTRY_DSN'),
        environment=env('SENTRY_ENVIRONMENT'),
        release=get_git_revision_hash(),
        integrations=[DjangoIntegration()]
    )

MIDDLEWARE = [
    'linkedevents.middleware.AwsAlbHeaderMiddleware',
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

# Internationalization

# Map language codes to the (code, name) tuples used by Django
# We want to keep the ordering in LANGUAGES configuration variable,
# thus some gyrations
language_map = {x: y for x, y in GLOBAL_LANGUAGES}
try:
    LANGUAGES = tuple((l, language_map[l]) for l in env('LANGUAGES'))
except KeyError as e:
    raise ImproperlyConfigured(f"unknown language code \"{e.args[0]}\"")
LANGUAGE_CODE = env('LANGUAGES')[0]

TIME_ZONE = 'Europe/Helsinki'

MUNIGEO_COUNTRY = 'country:fi'
MUNIGEO_MUNI = 'kunta:helsinki'

USE_I18N = True
USE_L10N = True
USE_TZ = True

LOCALE_PATHS = (
    os.path.join(BASE_DIR, 'locale'),
)

# Kulke importer looks here for its input files
IMPORT_FILE_PATH = os.path.join(BASE_DIR, 'data')

# Static files (CSS, JavaScript, Images)

STATIC_URL = env('STATIC_URL')
MEDIA_URL = env('MEDIA_URL')
STATIC_ROOT = env('STATIC_ROOT')
MEDIA_ROOT = env('MEDIA_ROOT')


# Configure django-storages for static files
STATICFILES_STORAGE = env('STATICFILES_STORAGE')
AWS_STORAGE_BUCKET_NAME = env('AWS_STATIC_STORAGE_BUCKET_NAME')
AWS_DEFAULT_ACL = env('AWS_STATIC_DEFAULT_ACL')
# The S3 files are served through nginx so we need to set the correct domain and path
AWS_S3_CUSTOM_DOMAIN = env('AWS_STATIC_S3_CUSTOM_DOMAIN')

# Configure django-storages for media files
# The other configuration options are defined in media_storage.py. See:
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#overriding-the-default-storage-class
DEFAULT_FILE_STORAGE = env('DEFAULT_FILE_STORAGE')
AWS_MEDIA_STORAGE_BUCKET_NAME = env('AWS_MEDIA_STORAGE_BUCKET_NAME')
AWS_MEDIA_DEFAULT_ACL = env('AWS_MEDIA_DEFAULT_ACL')
# The S3 files are served through nginx so we need to set the correct domain and path
AWS_MEDIA_S3_CUSTOM_DOMAIN = env('AWS_MEDIA_S3_CUSTOM_DOMAIN')

# Settings common to both static files and media files
# Do not append AWS query parameters to the generated URL
AWS_QUERYSTRING_AUTH = False

# A boolean that specifies whether to use the X-Forwarded-Host header in preference to the Host header. This should
# only be enabled if a proxy which sets this header is in use. If a proxy is in use and this is disabled, the links in
# the Browsable API will be wrong.
# See: https://docs.djangoproject.com/en/dev/ref/settings/#use-x-forwarded-host
USE_X_FORWARDED_HOST = env('USE_X_FORWARDED_HOST')

# A tuple representing a HTTP header/value combination that signifies a request is secure. This controls the behavior
# of the request object’s is_secure() method. Set this to ('HTTP_X_FORWARDED_PROTO', 'https') to tell Django to use the
# X-Forwarded-Proto header to tell whether the service is served over TLS or not. This can be used, e.g., when a proxy
# terminates the TLS connection and forwards the request over an unsecure HTTP connection. If a proxy is in use and
# this is disabled, the links in the Browsable API may show http as the scheme instead of https.
# See: https://docs.djangoproject.com/en/dev/ref/settings/#secure-proxy-ssl-header
SECURE_PROXY_SSL_HEADER = env('SECURE_PROXY_SSL_HEADER')

# Define the custom headers from which the X-Forwarded-{Port|Proto} header values will be copied. See middlewares.py
# for more details.
CUSTOM_X_FORWARDED_PORT_HEADER = env('CUSTOM_X_FORWARDED_PORT_HEADER')
CUSTOM_X_FORWARDED_PROTO_HEADER = env('CUSTOM_X_FORWARDED_PROTO_HEADER')

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
    'JWT_AUDIENCE': env('TOKEN_AUTH_ACCEPTED_AUDIENCE'),
    'JWT_SECRET_KEY': env('TOKEN_AUTH_SHARED_SECRET'),
}

CORS_ORIGIN_ALLOW_ALL = True
CSRF_COOKIE_NAME = '%s-csrftoken' % env('COOKIE_PREFIX')
SESSION_COOKIE_NAME = '%s-sessionid' % env('COOKIE_PREFIX')

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


def haystack_connection_for_lang(language_code):
    if language_code == "fi":
        return {'default-fi': {
                    'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
                    'BASE_ENGINE': 'events.custom_elasticsearch_search_backend.CustomEsSearchEngine',
                    'URL': env('ELASTICSEARCH_URL'),
                    'INDEX_NAME': 'linkedevents-fi',
                    'MAPPINGS': CUSTOM_MAPPINGS,
                    'SETTINGS': {
                        "analysis": {
                            "analyzer": {
                                "default": {
                                    "tokenizer": "finnish",
                                    "filter": ["lowercase", "voikko_filter"]
                                }
                            },
                            "filter": {
                                "voikko_filter": {
                                    "type": "voikko",
                                }
                            }
                        }
                    }
                },
                }
    else:
        return {f'default-{language_code}': {
                    'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
                    'BASE_ENGINE': 'events.custom_elasticsearch_search_backend.CustomEsSearchEngine',
                    'URL': env('ELASTICSEARCH_URL'),
                    'INDEX_NAME': f'linkedevents-{language_code}',
                    'MAPPINGS': CUSTOM_MAPPINGS,
                    }
                }


def dummy_haystack_connection_for_lang(language_code):
    return {f'default-{language_code}': {
                'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
                'BASE_ENGINE': 'haystack.backends.simple_backend.SimpleEngine'
                }
            }


HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.RealtimeSignalProcessor'

CUSTOM_MAPPINGS = {
    'autosuggest': {
        'search_analyzer': 'standard',
        'index_analyzer': 'edgengram_analyzer',
        'analyzer': None
    },
    'text': {
        'analyzer': 'default'
    }
}

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'multilingual_haystack.backends.MultilingualSearchEngine',
    }
}

for language in [l[0] for l in LANGUAGES]:
    if env('ELASTICSEARCH_URL'):
        connection = haystack_connection_for_lang(language)
    else:
        connection = dummy_haystack_connection_for_lang(language)
    HAYSTACK_CONNECTIONS.update(connection)


import bleach  # noqa
BLEACH_ALLOWED_TAGS = bleach.ALLOWED_TAGS + ["p", "div", "br"]

from easy_thumbnails.conf import Settings as thumbnail_settings  # noqa
THUMBNAIL_PROCESSORS = (
    'image_cropping.thumbnail_processors.crop_corners',
) + thumbnail_settings.THUMBNAIL_PROCESSORS

# django-orghierachy swappable model
DJANGO_ORGHIERARCHY_DATASOURCE_MODEL = 'events.DataSource'

AUTO_ENABLED_EXTENSIONS = env('AUTO_ENABLED_EXTENSIONS')

# shown in the browsable API
INSTANCE_NAME = env('INSTANCE_NAME')

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

SECRET_KEY = env('SECRET_KEY')

# We generate a persistent SECRET_KEY if it is not defined or it's empty. Note that
# setting SECRET_KEY will override the persisted key
if 'SECRET_KEY' not in locals() or not SECRET_KEY:
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
