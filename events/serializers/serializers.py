# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re

from rest_framework import serializers

from events.models import *
from fields import *
from django.conf import settings
from itertools import chain

# JSON exclusion list of MPTT's custom fields
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
    def convert_to_camelcase(s):
        return ''.join(word.title() if i else word for i, word in enumerate(s.split('_')))

    @staticmethod
    def convert_from_camelcase(s):
        return re.sub(r'(^|[a-z])([A-Z])',
                      lambda m: '_'.join([i.lower() for i in m.groups() if i]), s)

    def to_native(self, obj):
        """
        Before sending response there's a need to do additional work on to-be-JSON dictionary data
            1. Add @context and @type fields
            2. Convert underscored Django fields to Schema.org's camelCase format.
        """
        ret = self._dict_class()
        ret.fields = self._dict_class()

        if not self.hide_ld_context:
            ret['@context'] = 'http://schema.org'
        # use schema_org_type attribute present,
        # if not fallback to automatic resolution by model name.
        if hasattr(obj, 'schema_org_type'):
            ret['@type'] = obj.schema_org_type
        else:
            ret['@type'] = obj.__class__.__name__

        for field_name, field in self.fields.items():
            if field.read_only and obj is None:
                continue
            field.initialize(parent=self, field_name=field_name)
            key = LinkedEventsSerializer.convert_to_camelcase(self.get_field_key(field_name))
            value = field.field_to_native(obj, field_name)
            method = getattr(self, 'transform_%s' % field_name, None)
            if callable(method):
                value = method(obj, value)
            if not getattr(field, 'write_only', False):
                ret[key] = value
            ret.fields[key] = self.augment_field(field, field_name, key, value)
        return ret

    @staticmethod
    def rename_fields(dataz):
        if isinstance(dataz, dict):
            new_data = dict()
            for key, value in dataz.iteritems():
                newkey = LinkedEventsSerializer.convert_from_camelcase(key)
                if isinstance(value, (dict, list)):
                    new_data[newkey] = LinkedEventsSerializer.rename_fields(value)
                else:
                    new_data[newkey] = value
            return new_data
        elif isinstance(dataz, list):
            new_data = []
            for value in dataz:
                if isinstance(value, (dict, list)):
                    new_data.append(LinkedEventsSerializer.rename_fields(value))
                else:
                    new_data.append(value)
            return new_data

    def from_native(self, data, files):
        """
        Convert camelCased JSON fields to django/db friendly underscore format before validating/saving
        """
        converted_data = LinkedEventsSerializer.rename_fields(data)
        instance = super(LinkedEventsSerializer, self).from_native(converted_data, files)
        if not self._errors:
            return self.full_clean(instance)


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


class OpeningHoursSpecificationSerializer(LinkedEventsSerializer):
    class Meta:
        model = OpeningHoursSpecification


class PostalAddressSerializer(LinkedEventsSerializer):
    class Meta:
        model = PostalAddress


class GeoShapeSerializer(LinkedEventsSerializer):
    class Meta:
        model = GeoShape


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
    category = CategorySerializer(many=True, allow_add_remove=True, hide_ld_context=True)
    offers = OfferSerializer(many=True, allow_add_remove=True, hide_ld_context=True)
    event_status = EnumChoiceField(Event.STATUSES)

    class Meta(TranslationAwareSerializer.Meta):
        model = Event
        exclude = TranslationAwareSerializer.Meta.exclude + mptt_fields
