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
