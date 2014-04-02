# -*- coding: utf-8 -*-

import re
from lxml import etree
from django.utils.translation.trans_real import activate, deactivate

def clean_text(text):
    text = text.replace('\n', ' ')
    # remove consecutive whitespaces
    return re.sub(r'\s\s+', ' ', text, re.U).strip()

def unicodetext(item):
    if item is None or item.text is None:
        return None
    return clean_text(item.text)

def reduced_text(text):
    return re.sub(r'\W', '', text, flags=re.U).lower()

def text_match(a, b):
    return reduced_text(a) == reduced_text(b)

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
