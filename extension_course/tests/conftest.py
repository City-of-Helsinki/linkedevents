import pytest
from django.conf import settings
from django.core.management import call_command

from events.tests.conftest import (administrative_division, administrative_division_type, data_source, event,  # noqa
                                   location_id, minimal_event_dict, municipality, organization, place, user,
                                   user_api_client, django_db_modify_db_settings)


# Django test harness tries to serialize DB in order to support transactions
# within tests. (It restores the snapshot after such tests).
# This fails with modeltranslate, as the serialization is done before
# sync_translation_fields has a chance to run. Thus the fields are missing
# and serialization fails horribly.
#@pytest.fixture(scope='session')
#def django_db_modify_db_settings(django_db_modify_db_settings_xdist_suffix):
#    settings.DATABASES['default']['TEST']['SERIALIZE'] = False


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command('sync_translation_fields', '--noinput')


@pytest.fixture(autouse=True)
def auto_enable(settings):
    settings.AUTO_ENABLED_EXTENSIONS = ['course']
