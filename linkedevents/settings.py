"""
Django settings module for linkedevents project.
"""
import os
import subprocess

import bleach
import environ
import sentry_sdk
from django.conf.global_settings import LANGUAGES as GLOBAL_LANGUAGES
from django.core.exceptions import ImproperlyConfigured
from django_jinja.builtins import DEFAULT_EXTENSIONS
from easy_thumbnails.conf import Settings as thumbnail_settings  # noqa: N813
from sentry_sdk.integrations.django import DjangoIntegration

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
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, encoding="utf8"
        )
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
    ADMINS=(list, []),
    ALLOWED_HOSTS=(list, []),
    AUTO_ENABLED_EXTENSIONS=(list, []),
    COOKIE_PREFIX=(str, "linkedevents"),
    DATABASE_URL=(str, "postgis:///linkedevents"),
    DEBUG=(bool, False),
    ELASTICSEARCH_URL=(str, None),
    ENABLE_USER_DEFAULT_ORGANIZATION=(bool, False),
    EXTRA_INSTALLED_APPS=(list, []),
    INSTANCE_NAME=(str, "Linked Events"),
    INTERNAL_IPS=(list, []),
    LANGUAGES=(list, ["fi", "sv", "en", "zh-hans", "ru", "ar"]),
    LIPPUPISTE_EVENT_API_URL=(str, None),
    MAILGUN_API_URL=(str, ""),
    MAILGUN_SENDER_DOMAIN=(str, ""),
    MAILGUN_API_KEY=(str, ""),
    MEDIA_ROOT=(environ.Path(), root("media")),
    MEDIA_URL=(str, "/media/"),
    MEMCACHED_URL=(str, "127.0.0.1:11211"),
    SEAT_RESERVATION_DURATION=(int, 15),
    SECRET_KEY=(str, ""),
    SECURE_PROXY_SSL_HEADER=(tuple, None),
    SENTRY_DSN=(str, ""),
    SENTRY_ENVIRONMENT=(str, "development"),
    SOCIAL_AUTH_TUNNISTAMO_KEY=(str, "linkedevents-api-dev"),
    SOCIAL_AUTH_TUNNISTAMO_SECRET=(str, "dummy_key"),
    STATIC_ROOT=(environ.Path(), root("static")),
    STATIC_URL=(str, "/static/"),
    SUPPORT_EMAIL=(str, ""),
    SYSTEM_DATA_SOURCE_ID=(str, "system"),
    TOKEN_AUTH_ACCEPTED_AUDIENCE=(str, "https://api.hel.fi/auth/linkedevents"),
    TOKEN_AUTH_ACCEPTED_SCOPE_PREFIX=(str, "linkedevents"),
    TOKEN_AUTH_AUTHSERVER_URL=(str, "https://api.hel.fi/sso/openid"),
    TOKEN_AUTH_FIELD_FOR_CONSENTS=(str, "https://api.hel.fi/auth"),
    TOKEN_AUTH_REQUIRE_SCOPE_PREFIX=(bool, True),
    TOKEN_AUTH_SHARED_SECRET=(str, ""),
    TRUST_X_FORWARDED_HOST=(bool, False),
    USER_DEFAULT_ORGANIZATION_ID=(str, "others"),
)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = root()

# Django environ has a nasty habit of complanining at level
# WARN about env file not being preset. Here we pre-empt it.
env_file_path = os.path.join(BASE_DIR, CONFIG_FILE_NAME)
if os.path.exists(env_file_path):
    # Logging configuration is not available at this point
    print(f"Reading config from {env_file_path}")
    environ.Env.read_env(env_file_path)

DEBUG = env("DEBUG")
TEMPLATE_DEBUG = False

ALLOWED_HOSTS = env("ALLOWED_HOSTS")
ADMINS = env("ADMINS")
INTERNAL_IPS = env("INTERNAL_IPS", default=(["127.0.0.1"] if DEBUG else []))
DATABASES = {"default": env.db()}

DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

SYSTEM_DATA_SOURCE_ID = env("SYSTEM_DATA_SOURCE_ID")

SOCIAL_AUTH_TUNNISTAMO_KEY = env("SOCIAL_AUTH_TUNNISTAMO_KEY")
SOCIAL_AUTH_TUNNISTAMO_SECRET = env("SOCIAL_AUTH_TUNNISTAMO_SECRET")

SITE_ID = 1

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "timestamped_named": {
            "format": "%(asctime)s %(name)s %(levelname)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "timestamped_named",
        },
        # Just for reference, not used
        "blackhole": {
            "class": "logging.NullHandler",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
        },
        # Special configuration for elasticsearch, as INFO level prints
        # out every single call to elasticsearch
        "elasticsearch": {
            "level": "WARNING",
        },
    },
}

# Application definition
INSTALLED_APPS = [
    "helusers.apps.HelusersConfig",
    "helusers.apps.HelusersAdminConfig",
    "django.contrib.sites",
    "modeltranslation",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "debug_toolbar",
    # disable Django’s development server static file handling
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.postgres",
    "linkedevents",
    "events",
    "corsheaders",
    "rest_framework",
    "rest_framework_gis",
    "rest_framework_jwt",
    "mptt",
    "reversion",
    "haystack",
    "django_cleanup",
    "django_filters",
    "django_jinja",
    "notifications",
    "anymail",
    "helusers.providers.helsinki",
    "registrations",
    "helevents",
    "munigeo",
    "leaflet",
    "django_orghierarchy",
    "admin_auto_filters",
] + env("EXTRA_INSTALLED_APPS")

if env("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=env("SENTRY_DSN"),
        environment=env("SENTRY_ENVIRONMENT"),
        release=get_git_revision_hash(),
        integrations=[DjangoIntegration()],
    )

MIDDLEWARE = [
    # CorsMiddleware should be placed as high as possible and above WhiteNoiseMiddleware in particular
    "corsheaders.middleware.CorsMiddleware",
    # WhiteNoiseMiddleware should be placed as high as possible
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "reversion.middleware.RevisionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# django-extensions is a set of developer friendly tools
if DEBUG:
    INSTALLED_APPS.extend(["django_extensions"])


ROOT_URLCONF = "linkedevents.urls"

WSGI_APPLICATION = "linkedevents.wsgi.application"

# Internationalization

# Map language codes to the (code, name) tuples used by Django
# We want to keep the ordering in LANGUAGES configuration variable,
# thus some gyrations
language_map = {x: y for x, y in GLOBAL_LANGUAGES}
try:
    LANGUAGES = tuple((lang, language_map[lang]) for lang in env("LANGUAGES"))
except KeyError as e:
    raise ImproperlyConfigured(f'unknown language code "{e.args[0]}"')
LANGUAGE_CODE = env("LANGUAGES")[0]

TIME_ZONE = "Europe/Helsinki"

MUNIGEO_COUNTRY = "country:fi"
MUNIGEO_MUNI = "kunta:helsinki"

USE_I18N = True
USE_L10N = True
USE_TZ = True

LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)

# Kulke importer looks here for its input files
IMPORT_FILE_PATH = os.path.join(BASE_DIR, "data")

# Static files (CSS, JavaScript, Images)

STATIC_URL = env("STATIC_URL")
MEDIA_URL = env("MEDIA_URL")
STATIC_ROOT = env("STATIC_ROOT")
MEDIA_ROOT = env("MEDIA_ROOT")

# Whether to trust X-Forwarded-Host headers for all purposes
# where Django would need to make use of its own hostname
# fe. generating absolute URLs pointing to itself
# Most often used in reverse proxy setups
USE_X_FORWARDED_HOST = env("TRUST_X_FORWARDED_HOST")

#
# Authentication
#
AUTH_USER_MODEL = "helevents.User"
AUTHENTICATION_BACKENDS = (
    "helusers.tunnistamo_oidc.TunnistamoOIDCAuth",
    "django.contrib.auth.backends.ModelBackend",
)

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_ON_GET = True

# User will be assigned to a default organization if user doesn't have any
ENABLE_USER_DEFAULT_ORGANIZATION = env("ENABLE_USER_DEFAULT_ORGANIZATION")
# Default organization to which a user will be assigned if user doesn't
# have any organization. Default organization is created if it doesn't exist.
USER_DEFAULT_ORGANIZATION_ID = env("USER_DEFAULT_ORGANIZATION_ID")

#
# REST Framework
#
REST_FRAMEWORK = {
    "PAGE_SIZE": 20,
    "ORDERING_PARAM": "sort",
    "DEFAULT_RENDERER_CLASSES": (
        "events.renderers.JSONRenderer",
        "events.renderers.JSONLDRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "events.parsers.CamelCaseJSONParser",
        "events.parsers.JSONLDParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "events.api_pagination.CustomPagination",
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "events.auth.ApiKeyAuthentication",
        "events.auth.LinkedEventsJWTAuthentication",
    ),
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "VIEW_NAME_FUNCTION": "events.api.get_view_name",
}
JWT_AUTH = {
    "JWT_PAYLOAD_GET_USER_ID_HANDLER": "helusers.jwt.get_user_id_from_payload_handler",
    "JWT_AUDIENCE": env("TOKEN_AUTH_ACCEPTED_AUDIENCE"),
    "JWT_SECRET_KEY": env("TOKEN_AUTH_SHARED_SECRET"),
    "JWT_AUTH_HEADER_PREFIX": "Bearer",
}

CORS_ORIGIN_ALLOW_ALL = True
CSRF_COOKIE_NAME = "%s-csrftoken" % env("COOKIE_PREFIX")
SESSION_COOKIE_NAME = "%s-sessionid" % env("COOKIE_PREFIX")


TEMPLATES = [
    {
        "BACKEND": "django_jinja.backend.Jinja2",
        "APP_DIRS": True,
        "OPTIONS": {
            "extensions": DEFAULT_EXTENSIONS + ["jinja2.ext.i18n"],
            "translation_engine": "django.utils.translation",
            "match_extension": ".jinja",
            "filters": {"django_wordwrap": "django.template.defaultfilters.wordwrap"},
        },
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

POSTGIS_VERSION = (2, 1, 1)

WGS84_SRID = 4326  # WGS84 / GPS Spatial Reference System ID
# Use ETRS-TM35FIN projection by default
PROJECTION_SRID = 3067
# Bounding box of Finland and then some

BOUNDING_BOX = [-548576, 6291456, 1548576, 8388608]

CITYSDK_API_SETTINGS = {
    "CITYSDK_URL": "http://api.tourism.helsinki.citysdk.eu/CitySDK/",
    "USERNAME": "admin",
    "PASSWORD": "defaultCitySDKPassword",
    "SRS_URL": "http://www.opengis.net/def/crs/EPSG/0/%d" % PROJECTION_SRID,
    "DEFAULT_POI_CATEGORY": "53562f3238653c0a842a3bf7",
}

# Used in Lippupiste importer
LIPPUPISTE_EVENT_API_URL = env("LIPPUPISTE_EVENT_API_URL")

# Seat reservation duration in minutes
SEAT_RESERVATION_DURATION = env("SEAT_RESERVATION_DURATION")


def haystack_connection_for_lang(language_code):
    if language_code == "fi":
        return {
            "default-fi": {
                "ENGINE": "multilingual_haystack.backends.LanguageSearchEngine",
                "BASE_ENGINE": "events.custom_elasticsearch_search_backend.CustomEsSearchEngine",
                "URL": env("ELASTICSEARCH_URL"),
                "INDEX_NAME": "linkedevents-fi",
                "MAPPINGS": CUSTOM_MAPPINGS,
                "SETTINGS": {
                    "analysis": {
                        "analyzer": {
                            "default": {
                                "tokenizer": "finnish",
                                "filter": ["lowercase", "voikko_filter"],
                            }
                        },
                        "filter": {
                            "voikko_filter": {
                                "type": "voikko",
                            }
                        },
                    }
                },
            },
        }
    else:
        return {
            f"default-{language_code}": {
                "ENGINE": "multilingual_haystack.backends.LanguageSearchEngine",
                "BASE_ENGINE": "events.custom_elasticsearch_search_backend.CustomEsSearchEngine",
                "URL": env("ELASTICSEARCH_URL"),
                "INDEX_NAME": f"linkedevents-{language_code}",
                "MAPPINGS": CUSTOM_MAPPINGS,
            }
        }


def dummy_haystack_connection_for_lang(language_code):
    return {
        f"default-{language_code}": {
            "ENGINE": "multilingual_haystack.backends.LanguageSearchEngine",
            "BASE_ENGINE": "haystack.backends.simple_backend.SimpleEngine",
        }
    }


HAYSTACK_SIGNAL_PROCESSOR = "haystack.signals.RealtimeSignalProcessor"

CUSTOM_MAPPINGS = {
    "autosuggest": {
        "search_analyzer": "standard",
        "index_analyzer": "edgengram_analyzer",
        "analyzer": None,
    },
    "text": {"analyzer": "default"},
}

HAYSTACK_CONNECTIONS = {
    "default": {
        "ENGINE": "multilingual_haystack.backends.MultilingualSearchEngine",
    }
}

for language in [lang[0] for lang in LANGUAGES]:
    if env("ELASTICSEARCH_URL"):
        connection = haystack_connection_for_lang(language)
    else:
        connection = dummy_haystack_connection_for_lang(language)
    HAYSTACK_CONNECTIONS.update(connection)


BLEACH_ALLOWED_TAGS = frozenset(list(bleach.ALLOWED_TAGS) + ["p", "div", "br"])

THUMBNAIL_PROCESSORS = (
    "image_cropping.thumbnail_processors.crop_corners",
) + thumbnail_settings.THUMBNAIL_PROCESSORS

# django-orghierachy swappable model
DJANGO_ORGHIERARCHY_DATASOURCE_MODEL = "events.DataSource"

AUTO_ENABLED_EXTENSIONS = env("AUTO_ENABLED_EXTENSIONS")

# shown in the browsable API
INSTANCE_NAME = env("INSTANCE_NAME")

# local_settings.py can be used to override environment-specific settings
# like database and email that differ between development and production.
f = os.path.join(BASE_DIR, "local_settings.py")
if os.path.exists(f):
    import sys
    import types

    module_name = "%s.local_settings" % ROOT_URLCONF.split(".")[0]
    module = types.ModuleType(module_name)
    module.__file__ = f
    sys.modules[module_name] = module
    exec(open(f, "rb").read())

# We generate a persistent SECRET_KEY if it is not defined. Note that
# setting SECRET_KEY will override the persisted key
if "SECRET_KEY" not in locals():
    secret_file = os.path.join(BASE_DIR, ".django_secret")
    try:
        SECRET_KEY = open(secret_file).read().strip()
    except IOError:
        import random

        system_random = random.SystemRandom()
        try:
            SECRET_KEY = "".join(
                [
                    system_random.choice(
                        "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
                    )
                    for i in range(64)
                ]
            )
            secret = open(secret_file, "w")
            import os

            os.chmod(secret_file, 0o0600)
            secret.write(SECRET_KEY)
            secret.close()
        except IOError:
            Exception(
                "Please create a %s file with random characters to generate your secret key!"
                % secret_file
            )

#
# Anymail
#

if env("MAILGUN_API_KEY"):
    ANYMAIL = {
        "MAILGUN_API_KEY": env("MAILGUN_API_KEY"),
        "MAILGUN_SENDER_DOMAIN": env("MAILGUN_SENDER_DOMAIN"),
        "MAILGUN_API_URL": env("MAILGUN_API_URL"),
    }
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
elif not env("MAILGUN_API_KEY") and DEBUG is True:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION": env("MEMCACHED_URL"),
        "TIMEOUT": 300,
    },
    "ongoing_events": {
        "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION": env("MEMCACHED_URL"),
        "TIMEOUT": None,
        "OPTIONS": {
            "server_max_value_length": 1024 * 1024 * 500,
        },
    },
}

# this is relevant for the fulltext search as implemented in _filter_event_queryset()
FULLTEXT_SEARCH_LANGUAGES = {"fi": "finnish", "sv": "swedish", "en": "english"}

# Email address used to send feedback forms
SUPPORT_EMAIL = env("SUPPORT_EMAIL")

SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"


OIDC_API_TOKEN_AUTH = {
    "AUDIENCE": env.str("TOKEN_AUTH_ACCEPTED_AUDIENCE"),
    "API_SCOPE_PREFIX": env.str("TOKEN_AUTH_ACCEPTED_SCOPE_PREFIX"),
    "ISSUER": env.str("TOKEN_AUTH_AUTHSERVER_URL"),
    "API_AUTHORIZATION_FIELD": env.str("TOKEN_AUTH_FIELD_FOR_CONSENTS"),
    "REQUIRE_API_SCOPE_FOR_AUTHENTICATION": env.bool("TOKEN_AUTH_REQUIRE_SCOPE_PREFIX"),
}

OIDC_AUTH = {"OIDC_LEEWAY": 60 * 60}
