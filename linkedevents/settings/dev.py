"""Development server settings and globals."""


from base import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'linkedevents',
        'USER': 'linkedevents',
        'PASSWORD': 'linkedevents',
        'HOST': 'localhost',
        'PORT': '',
    }
}
