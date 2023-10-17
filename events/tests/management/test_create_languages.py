from io import StringIO

import pytest
from django.core.management import call_command
from pytest_django.asserts import assertNumQueries

from events.models import Language


@pytest.mark.no_use_audit_log
@pytest.mark.django_db
def test_create_languages():
    out = StringIO()

    call_command("create_languages", stdout=out)

    languages = Language.objects.all()
    assert languages.count() == 12
    for lang in languages:
        assert f"Created language {lang.pk}" in out.getvalue()
        assert lang.name_fi
        assert lang.name_sv
        assert lang.name_en


@pytest.mark.no_use_audit_log
@pytest.mark.django_db
def test_create_languages_check_should_create():
    """Re-running the command does a cheap check."""
    call_command("create_languages")

    with assertNumQueries(1):
        call_command("create_languages")
