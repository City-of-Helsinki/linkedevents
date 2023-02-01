import json
import os
import tempfile

import pytest
from django.core.management import call_command

from events.models import Event, Place
from linkedevents.management.commands.remap_events import DryRun


@pytest.mark.django_db
def test_remap_events(place, place2, event):
    with tempfile.TemporaryDirectory() as d:
        file_name = os.path.join(d, "test.json")
        with open(file_name, "w") as f:
            json.dump([[place.id, place2.id]], f)

        # Sanity check
        assert event.location_id == place.id
        assert place.id != place2.id

        # Check without --apply raises and makes no changes
        with pytest.raises(DryRun):
            call_command("remap_events", file_name)

        event.refresh_from_db()
        assert event.location_id == place.id

        # Check that with --apply changes are saved
        call_command("remap_events", file_name, "--apply")
        event.refresh_from_db()
        assert event.location_id == place2.id
