"""
Django settings module for linkedevents project.
"""

import importlib.util
import os
import subprocess
from datetime import datetime, timedelta
from urllib.parse import urljoin

import bleach
import environ
import sentry_sdk
from django.conf.global_settings import LANGUAGES as GLOBAL_LANGUAGES
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django_jinja.builtins import DEFAULT_EXTENSIONS
from easy_thumbnails.conf import Settings as thumbnail_settings  # noqa: N813
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber
from sentry_sdk.serializer import add_global_repr_processor

from linkedevents import __version__

CONFIG_FILE_NAME = "config_dev.env"

DEBUG_TOOLBAR_AVAILABLE = importlib.util.find_spec("debug_toolbar") is not None
DJANGO_EXTENSIONS_AVAILABLE = importlib.util.find_spec("django_extensions") is not None


def get_release_string() -> str:
    """
    Retrieve the git hash for the underlying openshift build or git repository.

    Will default to the version number if no git hash is available.
    """
    if build_commit := env("OPENSHIFT_BUILD_COMMIT"):
        return build_commit

    try:
        # We are not interested in gits complaints
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, encoding="utf8"
        )
    # If git or repository is not found, we will use the version number
    except (FileNotFoundError, subprocess.CalledProcessError):
        git_hash = __version__
    return git_hash.rstrip()


@add_global_repr_processor
def sentry_anonymize_user_repr(obj, hint):
    if isinstance(obj, get_user_model()):
        return f"<{obj.__class__.__name__}: {obj.username}>"

    return NotImplemented


root = environ.Path(__file__) - 2  # two levels back in hierarchy
env = environ.Env(
    ADMINS=(list, []),
    ALLOWED_HOSTS=(list, []),
    AUDIT_LOG_ENABLED=(bool, True),
    AUTO_ENABLED_EXTENSIONS=(list, []),
    COOKIE_PREFIX=(str, "linkedevents"),
    DATABASE_URL=(str, "postgis:///linkedevents"),
    DATABASE_PASSWORD=(str, ""),
    DEBUG=(bool, False),
    DEFAULT_FROM_EMAIL=(str, "noreply-linkedevents@hel.fi"),
    ELASTICSEARCH_URL=(str, None),
    ELIS_EVENT_API_URL=(
        str,
        "http://elis.helsinki1.hki.local/event-api/",
    ),
    EMAIL_HOST=(str, "relay.hel.fi"),
    EMAIL_PORT=(int, 25),
    EMAIL_USE_TLS=(bool, True),
    ENABLE_EXTERNAL_USER_EVENTS=(bool, True),
    ESPOO_API_URL=(str, "https://api.espoo.fi/events/"),
    ESPOO_API_EVENT_QUERY_PARAMS=(
        dict,
        {
            "publisher": "espoo:sito,espoo:tyt,espoo:koha,espoo:others,espoo:KOTO",
            "keyword": "yso:p2787",
        },
    ),
    ESPOO_API_EVENT_START_DAYS_BACK=(str, 180),
    ESPOO_API_PUBLISHERS=(
        list,
        [
            "espoo:sito;Elinvoima",
            "espoo:tyt;Kaupunkiympäristö",
            "espoo:koha;Konsernihallinto",
            "espoo:others;Muut",
            "espoo:KOTO;Kasvu ja oppiminen",
        ],
    ),
    ESPOO_MAX_PAGES=(int, 100),
    ESPOO_MAX_RETRIES=(int, 3),
    ESPOO_TIMEOUT=(int, 60),
    ESPOO_WAIT_BETWEEN=(float, 1.0),
    EXTERNAL_USER_PUBLISHER_ID=(str, "others"),
    ENKORA_API_USER=(str, "JoeEnkora"),
    ENKORA_API_PASSWORD=(str, None),
    EVENT_ADMIN_EXPIRATION_MONTHS=(int, 12),
    EXTRA_INSTALLED_APPS=(list, []),
    FIELD_ENCRYPTION_KEYS=(list, []),
    FINANCIAL_ADMIN_EXPIRATION_MONTHS=(int, 6),
    FULL_TEXT_WEIGHT_OVERRIDES=(dict, {}),
    GDPR_API_QUERY_SCOPE=(str, ""),
    GDPR_API_DELETE_SCOPE=(str, ""),
    GDPR_API_DELETE_EVENT_END_THRESHOLD_DAYS=(int, 30),
    GDPR_DISABLE_API_DELETION=(bool, True),
    HELUSERS_BACK_CHANNEL_LOGOUT_ENABLED=(bool, True),
    INSTANCE_NAME=(str, "Linked Events"),
    INTERNAL_IPS=(list, []),
    LANGUAGES=(list, ["fi", "sv", "en", "zh-hans", "ru", "ar"]),
    LIPPUPISTE_EVENT_API_URL=(str, None),
    LINKED_EVENTS_UI_URL=(str, "https://linkedevents.hel.fi"),
    LINKED_REGISTRATIONS_UI_URL=(
        str,
        "https://linkedregistrations-ui-prod.apps.platta.hel.fi",
    ),
    MEDIA_ROOT=(environ.Path(), root("media")),
    MEDIA_URL=(str, "/media/"),
    # "helsinki_adfs" = Tunnistamo auth_backends.adfs.helsinki.HelsinkiADFS
    # "helsinkiazuread" = Tunnistamo auth_backends.helsinki_azure_ad.HelsinkiAzureADTenantOAuth2  # noqa: E501
    # "helsinkiad" Helsinki Keycloak AD authentication
    # "vantaalinkedevents" Vantaa AD authentication in Helsinki Keycloak
    NON_EXTERNAL_AUTHENTICATION_METHODS=(
        list,
        ["helsinki_adfs", "helsinkiazuread", "helsinkiad", "vantaalinkedevents"],
    ),
    ANONYMIZATION_THRESHOLD_DAYS=(int, 30),
    OPENSHIFT_BUILD_COMMIT=(str, ""),
    STRONG_IDENTIFICATION_AUTHENTICATION_METHODS=(
        list,
        ["suomi_fi", "heltunnistussuomifi"],
    ),
    REDIS_SENTINELS=(list, []),
    REDIS_URL=(str, None),
    REDIS_PASSWORD=(str, None),
    SEAT_RESERVATION_DURATION=(int, 15),
    SECRET_KEY=(str, ""),
    SECURE_PROXY_SSL_HEADER=(tuple, None),
    SENTRY_DSN=(str, ""),
    SENTRY_ENVIRONMENT=(str, "development"),
    SOCIAL_AUTH_TUNNISTAMO_KEY=(str, "linkedevents-api-dev"),
    SOCIAL_AUTH_TUNNISTAMO_SECRET=(str, ""),
    SOCIAL_AUTH_TUNNISTAMO_OIDC_ENDPOINT=(str, ""),
    STATIC_ROOT=(environ.Path(), root("static")),
    STATIC_URL=(str, "/static/"),
    SUBSTITUTE_USER_ALLOWED_EMAIL_DOMAINS=(list, ["@hel.fi"]),
    SUPPORT_EMAIL=(str, ""),
    SWAGGER_USE_STATIC_SCHEMA=(bool, False),
    SYSTEM_DATA_SOURCE_ID=(str, "system"),
    TOKEN_AUTH_ACCEPTED_AUDIENCE=(list, ["https://api.hel.fi/auth/linkedevents"]),
    TOKEN_AUTH_ACCEPTED_SCOPE_PREFIX=(str, "linkedevents"),
    TOKEN_AUTH_AUTHSERVER_URL=(list, ["https://api.hel.fi/sso/openid"]),
    TOKEN_AUTH_FIELD_FOR_CONSENTS=(list, ["https://api.hel.fi/auth"]),
    TOKEN_AUTH_REQUIRE_SCOPE_PREFIX=(bool, False),
    TRUST_X_FORWARDED_HOST=(bool, False),
    REGISTRATION_ADMIN_EXPIRATION_MONTHS=(int, 6),
    REGISTRATION_USER_EXPIRATION_MONTHS=(int, 2),
    WEB_STORE_API_BASE_URL=(str, ""),
    WEB_STORE_API_KEY=(str, ""),
    WEB_STORE_API_NAMESPACE=(str, ""),
    WEB_STORE_INTEGRATION_ENABLED=(bool, False),
    WEB_STORE_ORDER_EXPIRATION_HOURS=(int, 48),
    WEB_STORE_WEBHOOK_API_KEY=(str, ""),
    WHITENOISE_STATIC_PREFIX=(str, "/static/"),
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
SECRET_KEY = env("SECRET_KEY")

ALLOWED_HOSTS = env("ALLOWED_HOSTS")
ADMINS = env("ADMINS")
INTERNAL_IPS = env("INTERNAL_IPS", default=(["127.0.0.1"] if DEBUG else []))
DATABASES = {"default": env.db()}

DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

if env("DATABASE_PASSWORD"):
    DATABASES["default"]["PASSWORD"] = env("DATABASE_PASSWORD")

SYSTEM_DATA_SOURCE_ID = env("SYSTEM_DATA_SOURCE_ID")

SOCIAL_AUTH_TUNNISTAMO_KEY = env("SOCIAL_AUTH_TUNNISTAMO_KEY")
SOCIAL_AUTH_TUNNISTAMO_SECRET = env("SOCIAL_AUTH_TUNNISTAMO_SECRET")
SOCIAL_AUTH_TUNNISTAMO_OIDC_ENDPOINT = env("SOCIAL_AUTH_TUNNISTAMO_OIDC_ENDPOINT")

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
    "social_django",
    "helusers.apps.HelusersConfig",
    "modeltranslation",
    "helusers.apps.HelusersAdminConfig",
    "django.contrib.sites",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    # disable Django’s development server static file handling
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.postgres",
    "corsheaders",
    "rest_framework",
    "rest_framework_gis",
    "knox",
    "mptt",
    "reversion",
    "haystack",
    "django_cleanup",
    "django_filters",
    "django_jinja",
    "munigeo",
    "leaflet",
    "django_orghierarchy",
    "admin_auto_filters",
    "encrypted_fields",
    "mailer",
    "drf_spectacular",
    # Local apps
    "linkedevents",
    "helevents",
    "notifications",
    "events",
    "registrations",
    "audit_log",
    "web_store",
    "data_analytics",
] + env("EXTRA_INSTALLED_APPS")

# django-extensions is a set of developer friendly tools
if DJANGO_EXTENSIONS_AVAILABLE:
    INSTALLED_APPS.extend(["django_extensions"])

COMMIT_HASH = get_release_string()
SENTRY_DENYLIST = DEFAULT_DENYLIST + [
    "access_code",
    "user_name",
    "user_email",
    "user_phone_number",
    "first_name",
    "last_name",
    "phone_number",
    "email",
    "city",
    "street_address",
    "zipcode",
    "postal_code",
    "date_of_birth",
    "membership_number",
    "native_language",
    "service_language",
    "extra_info",
]
if env("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=env("SENTRY_DSN"),
        environment=env("SENTRY_ENVIRONMENT"),
        release=COMMIT_HASH,
        integrations=[DjangoIntegration()],
        event_scrubber=EventScrubber(denylist=SENTRY_DENYLIST),
    )

MIDDLEWARE = [
    # CorsMiddleware should be placed as high as possible and above
    # WhiteNoiseMiddleware in particular
    "corsheaders.middleware.CorsMiddleware",
    # WhiteNoiseMiddleware should be placed as high as possible
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "events.middleware.AuthenticationCacheDisableMiddleware",
    "audit_log.middleware.AuditLogMiddleware",
    "reversion.middleware.RevisionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if DEBUG and DEBUG_TOOLBAR_AVAILABLE:
    import socket

    INSTALLED_APPS.extend(["debug_toolbar"])
    MIDDLEWARE.insert(
        MIDDLEWARE.index("whitenoise.middleware.WhiteNoiseMiddleware") + 1,
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )
    # Add the docker container gateway IP into internal IPs (for having debug toolbar)
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [ip[: ip.rfind(".")] + ".1" for ip in ips]


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
USE_TZ = True

LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)

# Static files (CSS, JavaScript, Images)

STATIC_URL = env("STATIC_URL")
MEDIA_URL = env("MEDIA_URL")
STATIC_ROOT = env("STATIC_ROOT")
MEDIA_ROOT = env("MEDIA_ROOT")
WHITENOISE_STATIC_PREFIX = env("WHITENOISE_STATIC_PREFIX")

# Do not try to chmod when uploading images.
# Our environments use persistent storage for media and operation will not be permitted.
# https://helsinkisolutionoffice.atlassian.net/wiki/spaces/HELFI/pages/7723876467/Storage#Operation-not-permitted
FILE_UPLOAD_PERMISSIONS = None

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


# Enable external user event create/update/delete.
ENABLE_EXTERNAL_USER_EVENTS = env("ENABLE_EXTERNAL_USER_EVENTS")

# Publisher used for events created by users without organization (i.e. external users)
EXTERNAL_USER_PUBLISHER_ID = env("EXTERNAL_USER_PUBLISHER_ID")

# Which OIDC authentication methods are never considered as external users
NON_EXTERNAL_AUTHENTICATION_METHODS = env("NON_EXTERNAL_AUTHENTICATION_METHODS")

# Which OIDC authentication methods are considered as strong identification methods
STRONG_IDENTIFICATION_AUTHENTICATION_METHODS = env(
    "STRONG_IDENTIFICATION_AUTHENTICATION_METHODS"
)

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
        "events.auth.ApiTokenAuthentication",
    ),
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "VIEW_NAME_FUNCTION": "linkedevents.utils.get_view_name",
}

CORS_ORIGIN_ALLOW_ALL = True
CSRF_COOKIE_NAME = "%s-csrftoken" % env("COOKIE_PREFIX")
SESSION_COOKIE_NAME = "%s-sessionid" % env("COOKIE_PREFIX")


TEMPLATES = [
    {
        "BACKEND": "django_jinja.jinja2.Jinja2",
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
                "django.template.context_processors.request",
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

# Urls to Linked Events UI and Linked Registration UI
LINKED_EVENTS_UI_URL = env("LINKED_EVENTS_UI_URL")
LINKED_REGISTRATIONS_UI_URL = env("LINKED_REGISTRATIONS_UI_URL")

# Used in kulke importer
ELIS_EVENT_API_URL = env("ELIS_EVENT_API_URL")


def haystack_connection_for_lang(language_code):
    if language_code == "fi":
        return {
            "default-fi": {
                "ENGINE": "multilingual_haystack.backends.LanguageSearchEngine",
                "BASE_ENGINE": "events.custom_elasticsearch_search_backend.CustomEsSearchEngine",  # noqa: E501
                "URL": env("ELASTICSEARCH_URL"),
                "INDEX_NAME": "linkedevents-fi",
                "SETTINGS": {
                    "analysis": {
                        "analyzer": {
                            "default": {
                                "tokenizer": "finnish",
                                "filter": ["lowercase", "raudikkoFilter"],
                            }
                        },
                        "filter": {"raudikkoFilter": {"type": "raudikko"}},
                    }
                },
            },
        }
    else:
        return {
            f"default-{language_code}": {
                "ENGINE": "multilingual_haystack.backends.LanguageSearchEngine",
                "BASE_ENGINE": "events.custom_elasticsearch_search_backend.CustomEsSearchEngine",  # noqa: E501
                "URL": env("ELASTICSEARCH_URL"),
                "INDEX_NAME": f"linkedevents-{language_code}",
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
            raise Exception(
                "Please create a %s file with random characters to generate your secret key!"  # noqa: E501
                % secret_file
            )

# Email configuration
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
SUPPORT_EMAIL = env("SUPPORT_EMAIL")  # Email address used to send feedback forms
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL"
)  # Email address used as default "from" email
EMAIL_BACKEND = "mailer.backend.DbBackend"
MAILER_USE_FILE_LOCK = False
MAILER_EMAIL_MAX_RETRIES = 5
if EMAIL_HOST and EMAIL_PORT:
    MAILER_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    if not DEBUG:
        print(
            "Warning: EMAIL_HOST and/or EMAIL_PORT not set, using console backend for sending "  # noqa: E501
            "emails"
        )
    MAILER_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Ongoing events will be cached forever
ONGOING_EVENTS_CACHE_TIMEOUT = None

if env("REDIS_URL"):
    # django.core.cache.backends.locmem.LocMemCache will be used as cache backend
    # if redis is not defined.
    DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
    SENTINELS = []

    if env("REDIS_SENTINELS"):
        DJANGO_REDIS_CONNECTION_FACTORY = "django_redis.pool.SentinelConnectionFactory"
        for sentinel in env("REDIS_SENTINELS"):
            host, port = sentinel.split(":")
            SENTINELS.append((host, port))

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": env("REDIS_URL"),
            "OPTIONS": (
                {
                    "CLIENT_CLASS": "django_redis.client.SentinelClient",
                    "CONNECTION_POOL_CLASS": "redis.sentinel.SentinelConnectionPool",
                    "PASSWORD": env("REDIS_PASSWORD"),
                    "SENTINELS": SENTINELS,
                    "SENTINEL_KWARGS": {"password": env("REDIS_PASSWORD")},
                    # Memcached like behavior for redis cache
                    # i.e. don't throw errors if redis is down.
                    "IGNORE_EXCEPTIONS": True,
                }
                if SENTINELS
                else {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "IGNORE_EXCEPTIONS": True,
                }
            ),
            "KEY_PREFIX": "linkedevents",
        }
    }

# this is relevant for the fulltext search as implemented in _filter_event_queryset()
FULLTEXT_SEARCH_LANGUAGES = {"fi": "finnish", "sv": "swedish", "en": "english"}

SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"

HELUSERS_BACK_CHANNEL_LOGOUT_ENABLED = env("HELUSERS_BACK_CHANNEL_LOGOUT_ENABLED")

OIDC_API_TOKEN_AUTH = {
    "AUDIENCE": env("TOKEN_AUTH_ACCEPTED_AUDIENCE"),
    "API_SCOPE_PREFIX": env("TOKEN_AUTH_ACCEPTED_SCOPE_PREFIX"),
    "ISSUER": env("TOKEN_AUTH_AUTHSERVER_URL"),
    "API_AUTHORIZATION_FIELD": env("TOKEN_AUTH_FIELD_FOR_CONSENTS"),
    "REQUIRE_API_SCOPE_FOR_AUTHENTICATION": env("TOKEN_AUTH_REQUIRE_SCOPE_PREFIX"),
}

OIDC_AUTH = {"OIDC_LEEWAY": 60 * 60}

# Enkora course importer
ENKORA_API_USER = env("ENKORA_API_USER")
ENKORA_API_PASSWORD = env("ENKORA_API_PASSWORD")

# GDPR API settings
GDPR_API_MODEL = "helevents.User"
GDPR_API_MODEL_LOOKUP = "uuid"
GDPR_API_URL_PATTERN = "v1/user/<uuid:uuid>"
GDPR_API_USER_PROVIDER = "helevents.utils.get_user_for_gdpr_api"
GDPR_API_DELETER = "helevents.utils.delete_user_and_gdpr_data"
GDPR_API_QUERY_SCOPE = env("GDPR_API_QUERY_SCOPE")
GDPR_API_DELETE_SCOPE = env("GDPR_API_DELETE_SCOPE")
GDPR_API_DELETE_EVENT_END_THRESHOLD_DAYS = env(
    "GDPR_API_DELETE_EVENT_END_THRESHOLD_DAYS"
)
GDPR_DISABLE_API_DELETION = env("GDPR_DISABLE_API_DELETION")

# A list of hex-encoded 32 byte keys used for encrypting sensitive data
FIELD_ENCRYPTION_KEYS = env("FIELD_ENCRYPTION_KEYS")

# Specify the number of days after which signup and signup groups will be anonymized
ANONYMIZATION_THRESHOLD_DAYS = env("ANONYMIZATION_THRESHOLD_DAYS")

ESPOO_API_URL = env("ESPOO_API_URL")
ESPOO_API_EVENT_QUERY_PARAMS = env("ESPOO_API_EVENT_QUERY_PARAMS")
ESPOO_API_EVENT_START_DAYS_BACK = env("ESPOO_API_EVENT_START_DAYS_BACK")
ESPOO_API_PUBLISHERS = [e.split(";", 1) for e in env("ESPOO_API_PUBLISHERS")]
ESPOO_MAX_PAGES = env("ESPOO_MAX_PAGES")
ESPOO_MAX_RETRIES = env("ESPOO_MAX_RETRIES")
ESPOO_TIMEOUT = env("ESPOO_TIMEOUT")
ESPOO_WAIT_BETWEEN = env("ESPOO_WAIT_BETWEEN")

# Audit log
AUDIT_LOG_ORIGIN = "linkedevents"
AUDIT_LOG_ENABLED = env("AUDIT_LOG_ENABLED")

FULL_TEXT_WEIGHT_OVERRIDES = env("FULL_TEXT_WEIGHT_OVERRIDES")

# Talpa web store integration
WEB_STORE_INTEGRATION_ENABLED = env("WEB_STORE_INTEGRATION_ENABLED")  # Temporary flag
WEB_STORE_API_BASE_URL = env("WEB_STORE_API_BASE_URL")
WEB_STORE_API_KEY = env("WEB_STORE_API_KEY")
WEB_STORE_API_NAMESPACE = env("WEB_STORE_API_NAMESPACE")
WEB_STORE_ORDER_EXPIRATION_HOURS = env("WEB_STORE_ORDER_EXPIRATION_HOURS")
WEB_STORE_WEBHOOK_API_KEY = env("WEB_STORE_WEBHOOK_API_KEY")

SUBSTITUTE_USER_ALLOWED_EMAIL_DOMAINS = env("SUBSTITUTE_USER_ALLOWED_EMAIL_DOMAINS")

REST_KNOX = {
    "AUTO_REFRESH": True,
    "TOKEN_MODEL": "data_analytics.DataAnalyticsApiToken",
    "TOKEN_PREFIX": "",
    "TOKEN_TTL": timedelta(days=30),
}

EVENT_ADMIN_EXPIRATION_MONTHS = env("EVENT_ADMIN_EXPIRATION_MONTHS")
FINANCIAL_ADMIN_EXPIRATION_MONTHS = env("FINANCIAL_ADMIN_EXPIRATION_MONTHS")
REGISTRATION_ADMIN_EXPIRATION_MONTHS = env("REGISTRATION_ADMIN_EXPIRATION_MONTHS")
REGISTRATION_USER_EXPIRATION_MONTHS = env("REGISTRATION_USER_EXPIRATION_MONTHS")

SWAGGER_USE_STATIC_SCHEMA = env("SWAGGER_USE_STATIC_SCHEMA")
SPECTACULAR_SETTINGS = {
    "TITLE": "Linked Events information API",
    "DESCRIPTION": (
        "Linked Events provides categorized data on events and places using JSON-LD format."  # noqa: E501
        "\n\n"
        "Events can be searched by date and location. Location can be exact address or larger "  # noqa: E501
        "area such as neighbourhood or borough."
        "\n\n"
        "JSON-LD format is streamlined using include mechanism. API users can request that certain "  # noqa: E501
        "fields are included directly into the result, instead of being hyperlinks to objects."  # noqa: E501
        "\n\n"
        "Several fields are multilingual. These are implemented as object with each language variant "  # noqa: E501
        "as property. In this specification each multilingual field has (fi,sv,en) property triplet as "  # noqa: E501
        "example."
    ),
    "VERSION": None,
    "SCHEMA_PATH_PREFIX": r"/v1/",
    "SCHEMA_PATH_PREFIX_TRIM": True,
    "PREPROCESSING_HOOKS": ["linkedevents.schema_utils.swagger_endpoint_filter"],
    "POSTPROCESSING_HOOKS": ["linkedevents.schema_utils.swagger_postprocessing_hook"],
    "GET_LIB_DOC_EXCLUDES": "linkedevents.schema_utils.swagger_get_lib_doc_excludes",
    "SERVERS": [
        {"url": "https://api.hel.fi/linkedevents/v1/"},
        {"url": "https://linkedevents.api.stage.hel.ninja/v1/"},
        {"url": "https://linkedevents.api.test.hel.ninja/v1/"},
        {"url": "https://linkedevents.api.dev.hel.ninja/v1/"},
    ],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
    },
    "TAGS": [
        {"name": "event", "description": "Search and edit events"},
        {"name": "search", "description": "Fulltext search through events and places"},
        {"name": "image", "description": "Get and upload images"},
        {"name": "keyword", "description": "Search and edit keywords"},
        {"name": "keyword_set", "description": "Search and edit keyword sets"},
        {"name": "organization", "description": "Search and edit organizations"},
        {"name": "place", "description": "Search and edit places"},
        {"name": "language", "description": "Get supported languages"},
        {"name": "data_source", "description": "Get supported data sources"},
        {
            "name": "organization_class",
            "description": "Get supported organization classes",
        },
        {"name": "registration", "description": "Search and edit registrations"},
        {
            "name": "registration_user_access",
            "description": "Send invitation email to registration user",
        },
        {
            "name": "seats_reservation",
            "description": "Create and edit seats reservations",
        },
        {"name": "signup", "description": "Search and edit signups"},
        {"name": "signup_group", "description": "Search and edit signup groups"},
        {"name": "user", "description": "Get users"},
    ],
}
if SWAGGER_USE_STATIC_SCHEMA:
    SPECTACULAR_SETTINGS["SWAGGER_UI_SETTINGS"]["url"] = urljoin(
        STATIC_URL, "openapi_schema.yaml"
    )
if WEB_STORE_INTEGRATION_ENABLED:
    SPECTACULAR_SETTINGS["TAGS"].append(
        {
            "name": "price_group",
            "description": "Create, edit and search customer group selections",
        }
    )

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

# get build time from a file in docker image
APP_BUILD_TIME = datetime.fromtimestamp(os.path.getmtime(__file__))
