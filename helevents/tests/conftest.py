import pytest
from django.conf import settings
from django.core.management import call_command

# Django test harness tries to serialize DB in order to support transactions
# within tests. (It restores the snapshot after such tests).
# This fails with modeltranslate, as the serialization is done before
# sync_translation_fields has a chance to run. Thus the fields are missing
# and serialization fails horribly.
@pytest.fixture(scope='session')
def django_db_modify_db_settings(django_db_modify_db_settings_xdist_suffix):
    settings.DATABASES['default']['TEST']['SERIALIZE'] = False


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command('sync_translation_fields', '--noinput')
