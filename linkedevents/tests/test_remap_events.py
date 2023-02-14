import json
import os
import tempfile

import pytest
from django.core.management import call_command


@pytest.mark.parametrize("apply", [True, False])
@pytest.mark.django_db
def test_remap_events(place, place2, event, apply):
    with tempfile.TemporaryDirectory() as d:
        file_name = os.path.join(d, "test.json")
        with open(file_name, "w") as f:
            json.dump({place.id: place2.id}, f)

        # Sanity check
        assert event.location_id == place.id
        assert place.id != place2.id

        args = ("--apply",) if apply else ()
        call_command("remap_events", file_name, *args)

        event.refresh_from_db()
        if apply:
            assert event.location_id == place2.id
        else:
            assert event.location_id == place.id
