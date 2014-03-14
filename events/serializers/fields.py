# -*- coding: utf-8 -*-
from django.conf import settings
from rest_framework import serializers
from events.models import Event


def get_value_from_tuple_list(list_of_tuples, search_key, value_index):
    """
    Find "value" from list of tuples by using the other value in tuple as a search key and other as a returned value
    :param list_of_tuples: tuples to be searched
    :param search_key: search key used to find right tuple
    :param value_index: Index telling which side of tuple is returned and which is used as a key
    :return: Value from either side of tuple
    """
    for i, v in enumerate(list_of_tuples):
        if v[value_index ^ 1] == search_key:
            return v[value_index]


class EnumChoiceField(serializers.WritableField):
    """
    Database value of tinyint is converted to and from a string representation of choice field

    TODO: Find if there's standardized way to render Schema.org enumeration instances in JSON-LD
    """

    def __init__(self, choices, prefix=''):
        self.choices = choices
        self.prefix = prefix
        super(EnumChoiceField, self).__init__()

    def to_native(self, obj):
        return self.prefix + get_value_from_tuple_list(self.choices, obj, 1)

    def from_native(self, data):
        return get_value_from_tuple_list(self.choices, self.prefix + data, 0)


class TranslatedField(serializers.WritableField):
    """
    Modeltranslation library generates i18n fields to given languages.
    Here i18n data is converted to more JSON friendly syntax.
    """
    def field_to_native(self, obj, field_name):
        # If source is given, use it as the attribute(chain) of obj to be
        # translated and ignore the original field_name
        if self.source:
            bits = self.source.split(".")
            field_name = bits[-1]
            for name in bits[:-1]:
                obj = getattr(obj, name)

        return {
            code: getattr(obj, field_name + "_" + code, None)
            for code, _ in settings.LANGUAGES
        }

    def field_from_native(self, data, files, field_name, into):
        super(TranslatedField, self).field_from_native(data, files, field_name, into)

        for code, value in data.get(field_name).iteritems():
            into[field_name + '_' + code] = value
            if code == settings.LANGUAGE_CODE:
                into[field_name] = value