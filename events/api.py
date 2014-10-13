# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from functools import wraps
from datetime import datetime, timedelta
from pprint import pprint

from django.utils import translation
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.core.urlresolvers import NoReverseMatch
from django.utils.datastructures import MultiValueDictKeyError
from django.contrib.gis.db.models.fields import GeometryField
from django.db import models as django_db_models
from django.db.models import Q, F
from django.shortcuts import get_object_or_404
from isodate import Duration, duration_isoformat, parse_duration
from rest_framework import serializers, pagination, relations, viewsets, filters, generics, fields
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from events.models import Place, Event, Keyword, Language, OpeningHoursSpecification, EventLink, Offer
from django.conf import settings
from events import utils
from events.custom_elasticsearch_search_backend import CustomEsSearchQuerySet as SearchQuerySet
from modeltranslation.translator import translator, NotRegistered
from django.utils.translation import ugettext_lazy as _
from dateutil.parser import parse as dateutil_parse
from haystack.query import AutoQuery

from munigeo.api import GeoModelSerializer, GeoModelAPIView, build_bbox_filter, srid_to_srs

import pytz


serializers_by_model = {}

all_views = []
def register_view(klass, name, base_name=None):
    entry = {'class': klass, 'name': name}
    if base_name is not None:
        entry['base_name'] = base_name
    all_views.append(entry)

    if klass.serializer_class and hasattr(klass.serializer_class.Meta, 'model'):
        model = klass.serializer_class.Meta.model
        serializers_by_model[model] = klass.serializer_class


class CustomPaginationSerializer(pagination.PaginationSerializer):
    results_field = 'data'
    def to_native(self, obj):
        ret = super(CustomPaginationSerializer, self).to_native(obj)
        meta_fields = ['count', 'next', 'previous']
        meta = {}
        for f in meta_fields:
            meta[f] = ret[f]
            del ret[f]
        ret['meta'] = meta
        if False: # FIXME: Check for JSON-LD
            try:
                ret['@context'] = obj.object_list.model.jsonld_context
            except (NameError, AttributeError):
                ret['@context'] = 'http://schema.org'
                pass
        return ret


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
        if isinstance(self.related_serializer, str):
            self.related_serializer = globals().get(self.related_serializer, None)
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

    # def get_field(self, model_field):
    #     kwargs = {}
    #     if issubclass(
    #             model_field.__class__,
    #                   (django_db_models.CharField,
    #                    django_db_models.TextField)):
    #         if model_field.null:
    #             kwargs['allow_none'] = True
    #         kwargs['max_length'] = getattr(model_field, 'max_length')
    #         return fields.CharField(**kwargs)
    #     return super(TranslatedModelSerializer, self).get_field(model_field)

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
    pagination_serializer_class = CustomPaginationSerializer

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

LOCAL_TZ = pytz.timezone(settings.TIME_ZONE)

class EventLinkSerializer(serializers.ModelSerializer):
    def to_native(self, obj):
        ret = super(EventLinkSerializer, self).to_native(obj)
        if not ret['name']:
            ret['name'] = None
        return ret

    class Meta:
        model = EventLink
        exclude = ['id']

class OfferSerializer(TranslatedModelSerializer):
    class Meta:
        model = Offer
        exclude = ['id', 'event']

class EventSerializer(LinkedEventsSerializer, GeoModelAPIView):
    location = JSONLDRelatedField(serializer=PlaceSerializer, required=False,
                                  view_name='place-detail')
    # provider = OrganizationSerializer(hide_ld_context=True)
    keywords = JSONLDRelatedField(serializer=KeywordSerializer, many=True, required=False,
                                    view_name='keyword-detail')
    super_event = JSONLDRelatedField(required=False, view_name='event-detail')
    event_status = EnumChoiceField(Event.STATUSES)
    external_links = EventLinkSerializer(many=True)
    offers = OfferSerializer(many=True)
    sub_events = JSONLDRelatedField(serializer='EventSerializer',
                                    required=False, view_name='event-detail', many=True)

    view_name = 'event-detail'

    def __init__(self, *args, skip_empties=False, skip_fields=set(), **kwargs):
        super(EventSerializer, self).__init__(*args, **kwargs)
        # The following can be used when serializing when
        # testing and debugging.
        self.skip_empties = skip_empties
        self.skip_fields = skip_fields

    def to_native(self, obj):
        ret = super(EventSerializer, self).to_native(obj)
        if 'start_time' in ret and not obj.has_start_time:
            # Return only the date part
            ret['start_time'] = obj.start_time.astimezone(LOCAL_TZ).strftime('%Y-%m-%d')
        if 'end_time' in ret and not obj.has_end_time:
            # If we're storing only the date part, do not pretend we have the exact time.
            if obj.end_time - obj.start_time <= timedelta(days=1):
                ret['end_time'] = None
        if hasattr(obj, 'days_left'):
            ret['days_left'] = int(obj.days_left)
        if self.skip_empties:
            for k in list(ret.keys()):
                val = ret[k]
                try:
                    if val is None or len(val) == 0:
                        del ret[k]
                except TypeError:
                    # not list/dict
                    pass
        for field in self.skip_fields:
            del ret[field]
        return ret

    class Meta:
        model = Event
        exclude = ['has_start_time', 'has_end_time', 'is_recurring_super']


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
            dt = datetime.utcnow().replace(tzinfo=pytz.utc)
            dt = dt.astimezone(LOCAL_TZ)
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
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

class LinkedEventsOrderingFilter(filters.OrderingFilter):
    ordering_param = 'sort'

class EventOrderingFilter(LinkedEventsOrderingFilter):
    def filter_queryset(self, request, queryset, view):
        queryset = super(EventOrderingFilter, self).filter_queryset(request, queryset, view)
        ordering = self.get_ordering(request)
        if not ordering:
            ordering = []
        if 'days_left' in [x.lstrip('-') for x in ordering]:
            queryset = queryset.extra(select={'days_left': 'date_part(\'day\', end_time - start_time)'})
        return queryset

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
    # Use select_ and prefetch_related() to reduce the amount of queries
    queryset = queryset.select_related('location')
    queryset = queryset.prefetch_related(
        'offers', 'keywords', 'external_links', 'sub_events')
    serializer_class = EventSerializer
    pagination_serializer_class = CustomPaginationSerializer
    filter_backends = (EventOrderingFilter,)
    ordering_fields = ('start_time', 'end_time', 'days_left')

    def get_object(self):
        # Overridden to prevent queryset filtering from being applied
        # outside list views.
        return get_object_or_404(Event.objects.all(), pk=self.kwargs['pk'])

    def filter_queryset(self, queryset):
        """
        TODO: convert to use proper filter framework
        """

        queryset = super(EventViewSet, self).filter_queryset(queryset)

        if 'show_all' not in self.request.QUERY_PARAMS:
            queryset = queryset.filter(
                Q(event_status=Event.SCHEDULED)
            )

        val = self.request.QUERY_PARAMS.get('start', None)
        if val:
            dt = parse_time(val, is_start=True)
            queryset = queryset.filter(Q(end_time__gt=dt) | Q(start_time__gte=dt))
        val = self.request.QUERY_PARAMS.get('end', None)
        if val:
            dt = parse_time(val, is_start=False)
            queryset = queryset.filter(Q(end_time__lt=dt) | Q(start_time__lte=dt))

        val = self.request.QUERY_PARAMS.get('bbox', None)
        if val:
            bbox_filter = build_bbox_filter(self.srs, val, 'position')
            places = Place.geo_objects.filter(**bbox_filter)
            queryset = queryset.filter(location__in=places)

        val = self.request.QUERY_PARAMS.get('data_source', None)
        if val:
            queryset = queryset.filter(data_source=val)

        val = self.request.QUERY_PARAMS.get('location', None)
        if val:
            queryset = queryset.filter(location_id=val)

        val = self.request.QUERY_PARAMS.get('keyword', None)
        if val:
            queryset = queryset.filter(keywords__pk=val)

        return queryset

register_view(EventViewSet, 'event')


class SearchSerializer(serializers.Serializer):
    def to_native(self, search_result):
        model = search_result.model
        assert model in serializers_by_model, "Serializer for %s not found" % model
        ser_class = serializers_by_model[model]
        data = ser_class(search_result.object, context=self.context).data
        data['object_type'] = model._meta.model_name
        data['score'] = search_result.score
        return data

DATE_DECAY_SCALE = '30d'

class SearchViewSet(GeoModelAPIView, viewsets.ViewSetMixin, generics.ListAPIView):
    serializer_class = SearchSerializer

    def list(self, request, *args, **kwargs):
        languages = [x[0] for x in settings.LANGUAGES]

        # If the incoming language is not specified, go with the default.
        self.lang_code = request.QUERY_PARAMS.get('language', languages[0])
        if self.lang_code not in languages:
            raise ParseError("Invalid language supplied. Supported languages: %s" %
                             ','.join(languages))

        input_val = request.QUERY_PARAMS.get('input', '').strip()
        q_val = request.QUERY_PARAMS.get('q', '').strip()
        if not input_val and not q_val:
            raise ParseError("Supply search terms with 'q=' or autocomplete entry with 'input='")
        if input_val and q_val:
            raise ParseError("Supply either 'q' or 'input', not both")

        old_language = translation.get_language()[:2]
        translation.activate(self.lang_code)

        queryset = SearchQuerySet()
        if input_val:
            queryset = queryset.filter(autosuggest=input_val)
            now = datetime.utcnow()
            queryset = queryset.filter(end_time__gt=now).decay({
                'gauss': {
                    'end_time': {
                        'origin': now,
                        'scale': DATE_DECAY_SCALE }}})
        else:
            queryset = queryset.filter(text=AutoQuery(q_val))

        self.object_list = queryset.load_all()

        # Switch between paginated or standard style responses
        page = self.paginate_queryset(self.object_list)
        if page is not None:
            serializer = self.get_pagination_serializer(page)
        else:
            serializer = self.get_serializer(self.object_list, many=True)

        resp = Response(serializer.data)

        translation.activate(old_language)

        return resp


register_view(SearchViewSet, 'search', base_name='search')
