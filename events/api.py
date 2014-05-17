# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from functools import wraps
from datetime import datetime, timedelta
from pprint import pprint

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.core.urlresolvers import NoReverseMatch
from django.utils.datastructures import MultiValueDictKeyError
from django.contrib.gis.db.models.fields import GeometryField
from django.db.models import Q
from isodate import Duration, duration_isoformat, parse_duration
from rest_framework import serializers, pagination, relations, viewsets
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from events.models import Place, Event, Keyword, Language, OpeningHoursSpecification
from django.conf import settings
from events import utils
from modeltranslation.translator import translator, NotRegistered
from django.utils.translation import ugettext_lazy as _
from dateutil.parser import parse as dateutil_parse
from munigeo.api import GeoModelSerializer, GeoModelAPIView, build_bbox_filter, srid_to_srs

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


class JSONLDRelatedField(relations.HyperlinkedRelatedField):
    """
    Support of showing and saving of expanded JSON nesting or just a resource
    URL.
    Serializing is controlled by query string param 'expand', deserialization
    by format of JSON given.

    Default serializing is expand=true.
    """

    invalid_json_error = _('Incorrect JSON. Expected JSON, received %s.')

    def __init__(self, *args, **kwargs):
        self.related_serializer = kwargs.pop('serializer', None)
        self.hide_ld_context = kwargs.pop('hide_ld_context', False)
        super(JSONLDRelatedField, self).__init__(*args, **kwargs)

    def to_native(self, obj):
        if self.is_expanded():
            return self.related_serializer(obj, hide_ld_context=self.hide_ld_context,
                                           context=self.context).data
        link = super(JSONLDRelatedField, self).to_native(obj)
        return {
            '@id': link
        }

    def from_native(self, value):
        if '@id' in value:
            return super(JSONLDRelatedField, self).from_native(value['@id'])
        else:
            raise ValidationError(
                self.invalid_json_error % type(value).__name__)

    def is_expanded(self):
        return getattr(self, 'expanded', False)


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
        if obj == None:
            return None
        return self.prefix + utils.get_value_from_tuple_list(self.choices,
                                                             obj, 1)

    def from_native(self, data):
        return utils.get_value_from_tuple_list(self.choices,
                                               self.prefix + data, 0)


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
        if 'created_by' in self.fields:
            del self.fields['created_by']
        if 'modified_by' in self.fields:
            del self.fields['modified_by']

        if context is not None:
            include_fields = context.get('include', [])
            for field_name in include_fields:
                if not field_name in self.fields:
                    continue
                field = self.fields[field_name]
                if not isinstance(field, JSONLDRelatedField):
                    continue
                field.expanded = True

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
        ret = super(LinkedEventsSerializer, self).to_native(obj)
        if 'id' in ret and 'request' in self.context:
            try:
                ret['@id'] = reverse(self.view_name,
                                        kwargs={u'pk': ret['id']},
                                        request=self.context['request'])
            except NoReverseMatch:
                ret['@id'] = str(value)

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
        # Note: Plan 'type' could be aliased to @type in context definition to
        # conform JSON-LD spec.
        if hasattr(obj, 'jsonld_type'):
            ret['@type'] = obj.jsonld_type
        else:
            ret['@type'] = obj.__class__.__name__

        return ret


class KeywordSerializer(LinkedEventsSerializer):
    view_name = 'keyword-detail'

    class Meta:
        model = Keyword

class KeywordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Keyword.objects.all()
    serializer_class = KeywordSerializer

register_view(KeywordViewSet, 'keyword')


class PlaceSerializer(LinkedEventsSerializer, GeoModelSerializer):
    view_name = 'place-detail'

    class Meta:
        model = Place


class PlaceViewSet(GeoModelAPIView, viewsets.ReadOnlyModelViewSet):
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


class EventSerializer(LinkedEventsSerializer, GeoModelAPIView):
    location = JSONLDRelatedField(serializer=PlaceSerializer, required=False,
                                  view_name='place-detail')
    # provider = OrganizationSerializer(hide_ld_context=True)
    keywords = JSONLDRelatedField(serializer=KeywordSerializer, many=True, required=False,
                                    view_name='keyword-detail')
    super_event = JSONLDRelatedField(required=False, view_name='event-detail')
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
            raise ParseError('time in invalid format (try ISO 8601 or yyyy-mm-dd)')
    return dt


class JSONAPIViewSet(viewsets.ReadOnlyModelViewSet):
    def initial(self, request, *args, **kwargs):
        ret = super(JSONAPIViewSet, self).initial(request, *args, **kwargs)
        self.srs = srid_to_srs(self.request.QUERY_PARAMS.get('srid', None))
        return ret

    def get_serializer_context(self):
        context = super(JSONAPIViewSet, self).get_serializer_context()

        include = self.request.QUERY_PARAMS.get('include', '')
        context['include'] = [x.strip() for x in include.split(',') if x]
        context['srs'] = self.srs

        return context

class EventViewSet(JSONAPIViewSet):
    """
    # Filtering retrieved events

    Query parameters can be used to filter the retrieved events by
    the following criteria.

    ## Event time

    Use `start` and `end` to restrict the date range of returned events.
    Any events that intersect with the given date range will be returned.

    The parameters `start` and `end` can be given in the following formats:

    - ISO 8601 (including the time of day)
    - yyyy-mm-dd

    In addition, `today` can be used as the value.

    Example:

        event/?start=2014-01-15&end=2014-01-20

    [See the result](?start=2014-01-15&end=2014-01-20 "json")

    ## Event location

    ### Bounding box

    To restrict the retrieved events to a geographical region, use
    the query parameter `bbox` in the format

        bbox=west,south,east,north

    Where `west` is the longitude of the rectangle's western boundary,
    `south` is the latitude of the rectangle's southern boundary,
    and so on.

    Example:

        event/?bbox=24.9348,60.1762,24.9681,60.1889

    [See the result](?bbox=24.9348,60.1762,24.9681,60.1889 "json")

    # Getting detailed data

    In the default case, keywords, locations, and other fields that
    refer to separate resources are only displayed as simple references.

    If you want to include the complete data from related resources in
    the current response, use the keyword `include`. For example:

        event/?include=location,keywords

    [See the result](?include=location,keywords "json")

    # Response data for the current URL

    """
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    pagination_serializer_class = CustomPaginationSerializer

    def filter_queryset(self, queryset):
        """
        TODO: convert to use proper filter framework
        """

        queryset = super(EventViewSet, self).filter_queryset(queryset)

        if 'show_all' not in self.request.QUERY_PARAMS:
            queryset = queryset.filter(Q(event_status=Event.SCHEDULED))

        val = self.request.QUERY_PARAMS.get('start', None)
        if val:
            dt = parse_time(val, is_start=True)
            queryset = queryset.filter(Q(end_time__gte=dt) | Q(start_time__gte=dt))
        val = self.request.QUERY_PARAMS.get('end', None)
        if val:
            dt = parse_time(val, is_start=False)
            queryset = queryset.filter(Q(end_time__lte=dt) | Q(start_time__lte=dt))

        val = self.request.QUERY_PARAMS.get('bbox', None)
        if val:
            bbox_filter = build_bbox_filter(self.srs, val, 'location')
            places = Place.geo_objects.filter(**bbox_filter)
            queryset = queryset.filter(location__in=places)

        return queryset

register_view(EventViewSet, 'event')
