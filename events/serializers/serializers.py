# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import serializers

from events.models import *
from fields import TranslatedField
from django.conf import settings
from itertools import chain

mptt_fields = ['lft', 'rght', 'tree_id', 'level']


class LinkedEventsSerializer(serializers.ModelSerializer):
    """Serializer with the support for JSON-LD/Schema.org.

    JSON-LD/Schema.org syntax::

      {
         "@context": "http://schema.org",
         "@type": "Event",
         "name": "Event name",
         ...
      }

    See full example at: http://schema.org/Event

    Args:
      hide_ld_context (bool): Hides `@context` from JSON, can be used in nested serializers

    """
    def __init__(self, instance=None, data=None, files=None,
                 context=None, partial=False, many=None,
                 allow_add_remove=False, hide_ld_context=False, **kwargs):
        super(LinkedEventsSerializer, self).__init__(instance, data, files,
                                                     context, partial, many,
                                                     allow_add_remove, **kwargs)
        self.hide_ld_context = hide_ld_context

    @staticmethod
    def convert_to_camel_case(word):
        return ''.join(word.title() if i else word for i, word in enumerate(word.split('_')))

    def to_native(self, obj):
        ret = self._dict_class()
        ret.fields = self._dict_class()

        if not self.hide_ld_context:
            ret['@context'] = 'http://schema.org'
        ret['@type'] = obj.__class__.__name__

        for field_name, field in self.fields.items():
            if field.read_only and obj is None:
                continue
            field.initialize(parent=self, field_name=field_name)
            key = LinkedEventsSerializer.convert_to_camel_case(self.get_field_key(field_name))
            value = field.field_to_native(obj, field_name)
            method = getattr(self, 'transform_%s' % field_name, None)
            if callable(method):
                value = method(obj, value)
            if not getattr(field, 'write_only', False):
                ret[key] = value
            ret.fields[key] = self.augment_field(field, field_name, key, value)

        return ret


class TranslationAwareSerializer(LinkedEventsSerializer):
    name = TranslatedField()
    description = TranslatedField()

    class Meta:
        exclude = list(chain.from_iterable((('name_' + code, 'description_' + code)
                                            for code, _ in settings.LANGUAGES)))


class CategorySerializer(TranslationAwareSerializer):
    class Meta(TranslationAwareSerializer.Meta):
        model = Category
        exclude = TranslationAwareSerializer.Meta.exclude + mptt_fields


class PlaceSerializer(TranslationAwareSerializer):
    class Meta(TranslationAwareSerializer.Meta):
        model = Place


class OrganizationSerializer(LinkedEventsSerializer):
    class Meta(TranslationAwareSerializer.Meta):
        model = Organization


class LanguageSerializer(LinkedEventsSerializer):
    class Meta(TranslationAwareSerializer.Meta):
        model = Language


class OfferSerializer(LinkedEventsSerializer):
    class Meta:
        model = Offer


class EventSerializer(TranslationAwareSerializer):
    location = PlaceSerializer(hide_ld_context=True)
    publisher = OrganizationSerializer(hide_ld_context=True)
    categories = CategorySerializer(many=True, allow_add_remove=True, hide_ld_context=True)
    offers = OfferSerializer(many=True, allow_add_remove=True, hide_ld_context=True)

    class Meta(TranslationAwareSerializer.Meta):
        model = Event
        exclude = TranslationAwareSerializer.Meta.exclude + mptt_fields
