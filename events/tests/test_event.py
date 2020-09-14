# -*- coding: utf-8 -*-
import pytest
from rest_framework.exceptions import ValidationError


@pytest.mark.django_db
def test_event_cannot_have_deprecated_keyword(event, keyword):
    keyword.deprecated = True
    keyword.save()
    event.keywords.set([keyword])
    with pytest.raises(ValidationError):
        event.save()
    event.keywords.set([])
    event.audience.set([keyword])
    with pytest.raises(ValidationError):
        event.save()


@pytest.mark.django_db
def test_deleted_event_can_have_deprecated_keyword(event, keyword):
    keyword.deprecated = True
    keyword.save()
    event.deleted = True
    event.save()
    event.keywords.set([keyword])
    event.save()
    event.keywords.set([])
    event.audience.set([keyword])
    event.save()


@pytest.mark.django_db
def test_event_cannot_replace_itself(event):
    event.replaced_by = event
    event.deprecated = True
    with pytest.raises(Exception):
        event.save()


@pytest.mark.django_db
def test_prevent_circular_event_replacement(event, event2, event3):
    event.replaced_by = event2
    event.save()
    event2.replaced_by = event3
    event2.save()
    event3.replaced_by = event
    with pytest.raises(Exception):
        event.save()
