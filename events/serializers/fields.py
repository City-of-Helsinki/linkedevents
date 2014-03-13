# -*- coding: utf-8 -*-
from django.conf import settings
from rest_framework import serializers
from events.models import Event


class EventStatusTypeField(serializers.WritableField):
    def to_native(self, obj):
        for i, v in enumerate(Event.STATUSES):
            if v[0] == obj:
                return v[1]

    def from_native(self, data):
        for i, v in enumerate(Event.STATUSES):
            if v[1] == data:
                return v[0]


class TranslatedField(serializers.WritableField):
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