# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from functools import wraps
from datetime import datetime, timedelta

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.core.urlresolvers import NoReverseMatch
from django.utils.datastructures import MultiValueDictKeyError
from isodate import Duration, duration_isoformat, parse_duration
from rest_framework import serializers, pagination, relations, viewsets
from rest_framework.reverse import reverse
from rest_framework.response import Response
from events.models import Place, Event, Category, Language, OpeningHoursSpecification
from django.conf import settings
from events import utils
from modeltranslation.translator import translator, NotRegistered
from django.utils.translation import ugettext_lazy as _
from dateutil.parser import parse as dateutil_parse
import pytz

all_views = []
def register_view(klass, name):
    all_views.append({'class': klass, 'name': name})


class CustomPaginationSerializer(pagination.PaginationSerializer):
    def to_native(self, obj):
        native = super(CustomPaginationSerializer, self).to_native(obj)
        try:
            native['@context'] = obj.object_list.model.jsonld_context
        except (NameError, AttributeError):
            native['@context'] = 'http://schema.org'
            pass
        return native


class JSONLDHyperLinkedRelatedField(relations.HyperlinkedRelatedField):
    invalid_json_error = _('Incorrect JSON.  Expected JSON, received %s.')

    def to_native(self, obj):
        link = super(JSONLDHyperLinkedRelatedField, self).to_native(obj)
        return {
            '@id': link
        }

    def from_native(self, value):
        if '@id' in value:
            return super(JSONLDHyperLinkedRelatedField,
                         self).from_native(value['@id'])
        else:
            raise ValidationError(
                self.invalid_json_error % type(value).__name__)


class JSONLDHyperLinkedRelatedFieldNested(JSONLDHyperLinkedRelatedField):
    """
    Support of showing and saving of expanded JSON nesting or just a resource
    URL.
    Serializing is controlled by query string param 'expand', deserialization
    by format of JSON given.

    Default serializing is expand=true.
    """
    invalid_json_error = _('Incorrect JSON.  Expected JSON, received %s.')

    def __init__(self, klass, *args, **kwargs):
        self.model = klass
        self.hide_ld_context = kwargs.pop('hide_ld_context', False)
        super(JSONLDHyperLinkedRelatedFieldNested, self).__init__(*args,
                                                                  **kwargs)

    def to_native(self, obj):
        if self.is_expanded():
            return self.model(obj, hide_ld_context=self.hide_ld_context,
                              context=self.context).data
        else:
            return super(JSONLDHyperLinkedRelatedFieldNested,
                         self).to_native(obj)

    def from_native(self, value):
        if '@id' in value and len(value) == 1:
            return super(JSONLDHyperLinkedRelatedField,
                         self).from_native(value['@id'])
        else:
            serializer = self.model()
            return serializer.from_native(value, None)

    def is_expanded(self):
        try:
            if self.context['request'].QUERY_PARAMS['expand'] == 'false':
                return False
            else:
                return True
        except MultiValueDictKeyError:
            return True


class EnumChoiceField(serializers.WritableField):
    """
    Database value of tinyint is converted to and from a string representation
    of choice field.

    TODO: Find if there's standardized way to render Schema.org enumeration
    instances in JSON-LD.
    """

    def __init__(self, choices, prefix=''):
        self.choices = choices
        self.prefix = prefix
        super(EnumChoiceField, self).__init__()

    def to_native(self, obj):
        return self.prefix + utils.get_value_from_tuple_list(self.choices,
                                                             obj, 1)

    def from_native(self, data):
        return utils.get_value_from_tuple_list(self.choices,
                                               self.prefix + data, 0)


class GeoPointField(serializers.WritableField):
    """
    Serialize GeoDjango field as proper looking GeoJSON
    """

    def from_native(self, data):
        if data is not None:
            if 'type' in data and data['type'] == 'Point' \
                    and 'coordinates' in data:
                return Point(data['coordinates'][0], data['coordinates'][1])
            else:
                raise ValidationError('Unexpected syntax of GeoJSON object')
        else:
            return super(GeoPointField, self).from_native(data)

    def field_to_native(self, obj, field_name):
        """
        GeoDjango provides it's own easy GeoJSON serialization by
        calling 'json', but to prevent escaping of raw JSON literal,
        GeoJSON is constructed here manually.

        :param obj: Object to be serialized
        :param field_name: Field to be serialized
        :return: Serialized field as a dict representation
        """
        if obj:
            if getattr(obj, field_name) is not None:
                return {
                    "type": "Point",
                    "coordinates": super(GeoPointField, self)
                    .field_to_native(obj, field_name)
                }
        else:
            return None


class ISO8601DurationField(serializers.WritableField):
    def to_native(self, obj):
        if obj:
            d = Duration(milliseconds=obj)
            return duration_isoformat(d)
        else:
            return None

    def from_native(self, data):
        if data:
            value = parse_duration(data)
            return (
                value.days * 24 * 3600 * 1000000
                + value.seconds * 1000
                + value.microseconds / 1000
            )
        else:
            return 0


class MPTTModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super(MPTTModelSerializer, self).__init__(*args, **kwargs)
        for field_name in 'lft', 'rght', 'tree_id', 'level':
            if field_name in self.fields:
                del self.fields[field_name]


class TranslatedModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super(TranslatedModelSerializer, self).__init__(*args, **kwargs)
        model = self.opts.model
        try:
            trans_opts = translator.get_options_for_model(model)
        except NotRegistered:
            self.translated_fields = []
            return

        self.translated_fields = trans_opts.fields.keys()
        lang_codes = [x[0] for x in settings.LANGUAGES]
        # Remove the pre-existing data in the bundle.
        for field_name in self.translated_fields:
            for lang in lang_codes:
                key = "%s_%s" % (field_name, lang)
                if key in self.fields:
                    del self.fields[key]
            del self.fields[field_name]

    def to_native(self, obj):
        ret = super(TranslatedModelSerializer, self).to_native(obj)
        if obj is None:
            return ret
        return self.translated_fields_to_native(obj, ret)

    def translated_fields_to_native(self, obj, ret):
        for field_name in self.translated_fields:
            d = {}
            default_lang = settings.LANGUAGES[0][0]
            d[default_lang] = getattr(obj, field_name)
            for lang in [x[0] for x in settings.LANGUAGES[1:]]:
                key = "%s_%s" % (field_name, lang)  
                val = getattr(obj, key, None)
                if val == None:
                    continue 
                d[lang] = val

            # If no text provided, leave the field as null
            for key, val in d.items():
                if val != None:
                    break
            else:
                d = None
            ret[field_name] = d

        return ret


class LinkedEventsSerializer(TranslatedModelSerializer, MPTTModelSerializer):
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
      hide_ld_context (bool):
        Hides `@context` from JSON, can be used in nested
        serializers
    """

    def __init__(self, instance=None, data=None, files=None,
                 context=None, partial=False, many=None,
                 allow_add_remove=False, hide_ld_context=False, **kwargs):
        super(LinkedEventsSerializer, self).__init__(instance, data, files,
                                                     context, partial, many,
                                                     allow_add_remove,
                                                     **kwargs)
        self.hide_ld_context = hide_ld_context

        self.disable_camelcase = True
        if 'request' in self.context:
            request = self.context['request']
            if 'disable_camelcase' in request.QUERY_PARAMS:
                self.disable_camelcase = True

    def to_native(self, obj):
        """
        Before sending to renderer there's a need to do additional work on
        to-be-JSON dictionary data:
            1. Add @context, @type and @id fields
            2. Convert field names to camelCase
        Renderer is the right place for this but now loop is done just once.
        Reversal conversion is done in parser.
        """
        ret = self._dict_class()
        ret.fields = self._dict_class()

        # Context is hidden if:
        # 1) hide_ld_context is set to True
        #   2) self.object is None, e.g. we are in the list of stuff
        if not self.hide_ld_context and self.object is not None:
            if hasattr(obj, 'jsonld_context') \
                    and isinstance(obj.jsonld_context, (dict, list)):
                ret['@context'] = obj.jsonld_context
            else:
                ret['@context'] = 'http://schema.org'

        # Use jsonld_type attribute if present,
        # if not fallback to automatic resolution by model name.
        # Note: Plan 'type' could be aliased to @type in context definition to
        # conform JSON-LD spec.
        if hasattr(obj, 'jsonld_type'):
            ret['@type'] = obj.jsonld_type
        else:
            ret['@type'] = obj.__class__.__name__

        for field_name, field in self.fields.items():
            if field.read_only and obj is None:
                continue
            field.initialize(parent=self, field_name=field_name)
            if self.disable_camelcase:
                key = self.get_field_key(field_name)
            else:
                key = utils.convert_to_camelcase(self.get_field_key(field_name))
            value = field.field_to_native(obj, field_name)
            if field_name == 'id':
                if 'request' in self.context:
                    try:
                        ret['@id'] = reverse(self.view_name,
                                             kwargs={u'pk': value},
                                             request=self.context['request'])
                    except NoReverseMatch:
                        ret['@id'] = str(value)
            method = getattr(self, 'transform_%s' % field_name, None)
            if callable(method):
                value = method(obj, value)
            if not getattr(field, 'write_only', False):
                ret[key] = value
            ret.fields[key] = self.augment_field(field, field_name, key, value)

        return self.translated_fields_to_native(obj, ret)

    class Meta:
        exclude = ['created_by', 'modified_by']


class CategorySerializer(LinkedEventsSerializer):
    category_for = EnumChoiceField(Category.CATEGORY_TYPES)

    class Meta:
        model = Category


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

register_view(CategoryViewSet, 'category')


class PlaceSerializer(LinkedEventsSerializer):
    location = GeoPointField(required=False)

    view_name = 'place-detail'

    class Meta:
        model = Place


class PlaceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer
    pagination_serializer_class = CustomPaginationSerializer

register_view(PlaceViewSet, 'place')


class OpeningHoursSpecificationSerializer(LinkedEventsSerializer):
    class Meta:
        model = OpeningHoursSpecification


class LanguageSerializer(LinkedEventsSerializer):
    view_name = 'language-detail'

    class Meta:
        model = Language


class LanguageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer

register_view(LanguageViewSet, 'language')


class SubOrSuperEventSerializer(TranslatedModelSerializer, MPTTModelSerializer):
    location = PlaceSerializer(hide_ld_context=True)
    category = CategorySerializer(many=True, allow_add_remove=True,
                                  hide_ld_context=True)
    super_event = JSONLDHyperLinkedRelatedField(view_name='event-detail')

    class Meta:
        model = Event


class EventSerializer(TranslatedModelSerializer, MPTTModelSerializer):
    location = JSONLDHyperLinkedRelatedField(required=False,
                                             view_name='place-detail')
    # provider = OrganizationSerializer(hide_ld_context=True)
    categories = CategorySerializer(many=True, allow_add_remove=True,
                                    hide_ld_context=True)
    super_event = JSONLDHyperLinkedRelatedField(required=False,
                                                view_name='event-detail')
    event_status = EnumChoiceField(Event.STATUSES)

    view_name = 'event-detail'

    class Meta:
        model = Event


LOCAL_TZ = pytz.timezone(settings.TIME_ZONE)

def parse_time(time_str, is_start):
    time_str = time_str.strip()
    # Handle dates first. Assume dates are given in local timezone.
    # FIXME: What if there's no local timezone?
    try:
        dt = datetime.strptime(time_str, '%Y-%m-%d')
        dt = dt.replace(tzinfo=LOCAL_TZ)
    except ValueError:
        dt = None
    if not dt:
        if time_str.lower() == 'today':
            dt = datetime.now().replace(hour=0, minute=0, microsecond=0)
    if dt:
        # With start timestamps, we treat dates as beginning
        # at midnight the same day. End timestamps are taken to
        # mean midnight on the following day.
        if not is_start:
            dt = dt + timedelta(days=1)
    else:
        try:
            # Handle all other times through dateutil.
            dt = dateutil_parse(time_str)
        except TypeError:
            return None
    return dt

class EventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    pagination_serializer_class = CustomPaginationSerializer

    def list(self, request, *args, **kwargs):
        """
        TODO: convert to use proper filter framework
        """
        args = {} if 'show_all' in request.QUERY_PARAMS else {
            'event_status': Event.SCHEDULED}

        if 'from' in request.QUERY_PARAMS:
            dt = parse_time(request.QUERY_PARAMS['from'], is_start=True)
            if dt:
                args['start_time__gte'] = dt

        if 'to' in request.QUERY_PARAMS:
            dt = parse_time(request.QUERY_PARAMS['to'], is_start=False)
            if dt:
                args['end_time__lte'] = dt

        self.queryset = Event.objects.filter(**args)

        return super(EventViewSet, self).list(request, *args, **kwargs)

register_view(EventViewSet, 'event')
