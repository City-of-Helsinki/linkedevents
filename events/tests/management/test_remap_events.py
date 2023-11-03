import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command


def create_remap_file(tmp_path: Path, data: dict[str, str]) -> Path:
    path = tmp_path / "test.json"
    path.write_text(json.dumps(data))
    return path


@pytest.mark.no_test_audit_log
@pytest.mark.django_db
def test_remap_events_with_apply(tmp_path, place, place2, event):
    remap_path = create_remap_file(tmp_path, {place.id: place2.id})

    # Sanity check
    assert event.location_id == place.id
    assert place.id != place2.id

    out = StringIO()
    call_command("remap_events", remap_path, "--apply", stdout=out)

    event.refresh_from_db()
    assert event.location_id == place2.id
    assert "1 events updated" in out.getvalue()
    assert "Done" in out.getvalue()


@pytest.mark.no_test_audit_log
@pytest.mark.django_db
def test_remap_events_without_apply(tmp_path, place, place2, event):
    remap_path = create_remap_file(tmp_path, {place.id: place2.id})

    # Sanity check
    assert event.location_id == place.id
    assert place.id != place2.id

    out = StringIO()
    call_command("remap_events", remap_path, stdout=out)

    event.refresh_from_db()
    assert event.location_id == place.id
    assert "1 events updated" in out.getvalue()
    assert "no changes applied" in out.getvalue()


@pytest.mark.no_test_audit_log
@pytest.mark.django_db
def test_remap_events_target_does_not_exist(tmp_path, place, event):
    remap_path = create_remap_file(tmp_path, {place.id: "does_not_exist:1234"})
    err = StringIO()
    call_command("remap_events", remap_path, "--apply", stderr=err)

    event.refresh_from_db()
    assert event.location_id == place.id
    assert (
        "Failed to apply: New place does_not_exist:1234 does not exist"
        in err.getvalue()
    )
