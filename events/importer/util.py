# -*- coding: utf-8 -*-

import re
from django.utils.translation.trans_real import activate, deactivate


def clean_text(text):
    return re.sub(r'\W', '', text, flags=re.U).lower()


def text_match(a, b):
    return clean_text(a) == clean_text(b)


def address_eq(a, b):
    if ('postal_code' in a and 'postal_code' in b and
       a['postal_code'] != b['postal_code']):
        return False
    for key in ['locality', 'street_address']:
        languages = a[key].viewkeys() | b[key].viewkeys()
        for l in languages:
            if (l in a[key] and l in b[key] and not
               text_match(a[key][l], b[key][l])):
                return False
    return True


class active_language:
    def __init__(self, language):
        self.language = language

    def __enter__(self):
        activate(self.language)
        return self.language

    def __exit__(self, type, value, traceback):
        deactivate()
