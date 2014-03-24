"""
WSGI config for linkedevents project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/howto/deployment/wsgi/
"""

import os
if os.environ.get('PRODUCTION', None):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "linkedevents.prod")
elif os.environ.get('CD', None):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "linkedevents.cd")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "linkedevents.dev")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
