"""Continuous deployment settings and globals."""

from base import *


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ.get('SQL_DB', None),
        'USER': os.environ.get('SQL_USERNAME', None),
        'PASSWORD': os.environ.get('SQL_PASSWORD', None),
        'HOST': os.environ.get('SQL_HOST', None),
        'PORT': os.environ.get('SQL_PORT', None),
    }
}
