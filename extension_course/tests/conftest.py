import pytest
from events.tests.conftest import (administrative_division, administrative_division_type, data_source, event,  # noqa
                                   location_id, minimal_event_dict, municipality, organization, place, user,
                                   user_api_client, django_db_modify_db_settings, django_db_setup)


@pytest.fixture(autouse=True)
def auto_enable(settings):
    settings.AUTO_ENABLED_EXTENSIONS = ['course']
