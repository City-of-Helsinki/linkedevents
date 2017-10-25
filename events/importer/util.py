# -*- coding: utf-8 -*-

import re
from django.utils.translation.trans_real import activate, deactivate

from events.models import Place


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


def replace_location(replace=None,
                     from_source='tprek',
                     by=None,
                     by_source='matko',
                     include_deleted=False):
    """
    Takes two locations from different data sources and replaces one by the other. If one or the other is
    not provided, the other is found by the name of the other and the specified data source.

    :param replace: The location to be replaced
    :param from_datasource: The data source to look for the location to be replaced
    :param by: The location to replace by
    :param by_datasource: The data source to look for the location to replace by
    :param include_deleted: Include deleted locations when looking for replacements
    :return: Boolean that determines whether a new location was found for the hapless events
    """
    if not by:
        replacements = Place.objects.filter(name__iexact=replace.name, data_source=by_source, deleted=False)
        if replacements.count() == 1:
            by = replacements[0]
        else:
            # the backup is to look for deleted locations and reinstate them
            if include_deleted:
                replacements = Place.objects.filter(name__iexact=replace.name, data_source=by_source)
                if replacements.count() == 1:
                    by = replacements[0]
                else:
                    # no replacement whatsoever was found, this may result in an exception
                    return False
            else:
                return False
    if not replace:
        to_be_replaced = Place.objects.filter(name__iexact=by.name, data_source=from_source)
        if to_be_replaced.count() == 1:
            replace = to_be_replaced[0]
        # if no place to be replaced was found, it's alright, we might have a brand new location here!
    by.deleted = False
    by.replaced_by = None
    by.save(update_fields=['deleted', 'replaced_by'])
    if replace:
        replace.deleted = True
        replace.replaced_by = by
        replace.save(update_fields=['deleted', 'replaced_by'])
        print("Location %s (%s) was deleted. Discovered replacement location %s" %
              (replace.id, str(replace), by.id))
    return True


class active_language:
    def __init__(self, language):
        self.language = language

    def __enter__(self):
        activate(self.language)
        return self.language

    def __exit__(self, type, value, traceback):
        deactivate()
