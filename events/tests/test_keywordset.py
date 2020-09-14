# -*- coding: utf-8 -*-
import pytest
from rest_framework.exceptions import ValidationError


@pytest.mark.django_db
def test_keywordset_cannot_have_deprecated_keyword(keyword, keyword_set):
    keyword.deprecated = True
    keyword.save()
    with pytest.raises(ValidationError):
        keyword_set.save()
