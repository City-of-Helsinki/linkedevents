# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from itertools import chain

from django.conf import settings

from events import utils
from events.models import *
from fields import *
from events.utils import get_value_from_tuple_list

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

    def to_native(self, obj):
        """
        Before sending to renderer there's a need to do additional work on to-be-JSON dictionary data
            1. Add @context and @type fields
            2. Convert field names to camelCase,
            renderer is the right place for this but now loop is done just once. Reversal conversion is done in parser.
        """
        ret = self._dict_class()
        ret.fields = self._dict_class()

        if not self.hide_ld_context:
            if hasattr(obj, 'jsonld_context') and isinstance(obj.jsonld_context, (dict, list)):
                ret['@context'] = obj.jsonld_context
            else:
                ret['@context'] = 'http://schema.org'
        # use schema_org_type attribute present,
        # if not fallback to automatic resolution by model name.
        if hasattr(obj, 'jsonld_type'):
            ret['@type'] = obj.jsonld_type
        else:
            ret['@type'] = obj.__class__.__name__

        for field_name, field in self.fields.items():
            if field.read_only and obj is None:
                continue
            field.initialize(parent=self, field_name=field_name)
            key = utils.convert_to_camelcase(self.get_field_key(field_name))
            value = field.field_to_native(obj, field_name)
            method = getattr(self, 'transform_%s' % field_name, None)
            if callable(method):
                value = method(obj, value)
            if not getattr(field, 'write_only', False):
                ret[key] = value
            ret.fields[key] = self.augment_field(field, field_name, key, value)
        return ret

    class Meta:
        exclude = ['created_by', 'modified_by']


class TranslationAwareSerializer(LinkedEventsSerializer):
    name = TranslatedField()
    description = TranslatedField()

    class Meta(LinkedEventsSerializer.Meta):
        exclude = LinkedEventsSerializer.Meta.exclude + list(chain.from_iterable((
            ('name_' + code, 'description_' + code) for code, _ in settings.LANGUAGES)))


class PersonSerializer(TranslationAwareSerializer):
    # Fallback to URL references to get around of circular serializer problem
    creator = serializers.HyperlinkedRelatedField(view_name='person-detail')
    editor = serializers.HyperlinkedRelatedField(view_name='person-detail')

    class Meta(TranslationAwareSerializer.Meta):
        model = Person
        exclude = TranslationAwareSerializer.Meta.exclude + mptt_fields


class CategorySerializer(TranslationAwareSerializer):
    creator = PersonSerializer(hide_ld_context=True)
    editor = PersonSerializer(hide_ld_context=True)
    category_for = EnumChoiceField(Category.CATEGORY_TYPES)

    class Meta(TranslationAwareSerializer.Meta):
        model = Category
        exclude = TranslationAwareSerializer.Meta.exclude + mptt_fields


class GeoInfoSerializer(LinkedEventsSerializer):
    """
    Serializer renders GeoShape or GeoCoordinate style JSON object depending on geo_type field
    """
    class Meta:
        model = GeoInfo
        exclude = ["place", "geo_type"]

    def to_native(self, obj):
        exclude_fields = ['longitude', 'latitude'] if obj.geo_type == GeoInfo.GEO_TYPES[0][0] \
            else ['box', 'circle', 'line', 'polygon']
        for field_name in exclude_fields:
            if field_name in self.fields:
                del self.fields[field_name]
        return super(GeoInfoSerializer, self).to_native(obj)

    def from_native(self, data, files):
        if data['@type'] in ('GeoShape', 'GeoCoordinates'):
            data['geo_type'] = get_value_from_tuple_list(GeoInfo.GEO_TYPES, data['@type'], 0)

        return super(GeoInfoSerializer, self).from_native(data, files)


class PlaceSerializer(TranslationAwareSerializer):
    creator = PersonSerializer(hide_ld_context=True)
    editor = PersonSerializer(hide_ld_context=True)
    geo = GeoInfoSerializer(hide_ld_context=True)

    class Meta(TranslationAwareSerializer.Meta):
        model = Place
        exclude = TranslationAwareSerializer.Meta.exclude + mptt_fields


class OpeningHoursSpecificationSerializer(LinkedEventsSerializer):
    class Meta(LinkedEventsSerializer.Meta):
        model = OpeningHoursSpecification


class PostalAddressSerializer(LinkedEventsSerializer):
    class Meta(LinkedEventsSerializer.Meta):
        model = PostalAddress


class OrganizationSerializer(LinkedEventsSerializer):
    creator = PersonSerializer(hide_ld_context=True)
    editor = PersonSerializer(hide_ld_context=True)

    class Meta(TranslationAwareSerializer.Meta):
        model = Organization


class LanguageSerializer(LinkedEventsSerializer):
    class Meta(TranslationAwareSerializer.Meta):
        model = Language


class OfferSerializer(LinkedEventsSerializer):
    class Meta(LinkedEventsSerializer.Meta):
        model = Offer


class SubOrSuperEventSerializer(TranslationAwareSerializer):
    location = PlaceSerializer(hide_ld_context=True)
    publisher = OrganizationSerializer(hide_ld_context=True)
    category = CategorySerializer(many=True, allow_add_remove=True, hide_ld_context=True)
    offers = OfferSerializer(hide_ld_context=True)
    creator = serializers.HyperlinkedRelatedField(many=True,view_name='person-detail')
    editor = serializers.HyperlinkedRelatedField(view_name='person-detail')
    super_event = serializers.HyperlinkedRelatedField(view_name='event-detail')

    class Meta(TranslationAwareSerializer.Meta):
        model = Event
        exclude = TranslationAwareSerializer.Meta.exclude + mptt_fields


class EventSerializer(TranslationAwareSerializer):
    location = PlaceSerializer(hide_ld_context=True)
    publisher = OrganizationSerializer(hide_ld_context=True)
    category = CategorySerializer(many=True, allow_add_remove=True, hide_ld_context=True)
    offers = OfferSerializer(hide_ld_context=True)
    creator = PersonSerializer(many=True, hide_ld_context=True)
    editor = PersonSerializer(hide_ld_context=True)
    super_event = SubOrSuperEventSerializer(hide_ld_context=True)
    sub_event = SubOrSuperEventSerializer(many=True, hide_ld_context=True)

    event_status = EnumChoiceField(Event.STATUSES)

    class Meta(TranslationAwareSerializer.Meta):
        model = Event
        exclude = TranslationAwareSerializer.Meta.exclude + mptt_fields
