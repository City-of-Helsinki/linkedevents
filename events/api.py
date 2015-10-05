# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# python
import base64
import re
import struct
import time
import urllib
import urllib.parse
from datetime import datetime, timedelta

# django
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.urlresolvers import NoReverseMatch
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import translation
from django.utils.translation import ugettext_lazy as _

# 3rd party
import pytz
from dateutil.parser import parse as dateutil_parse
from haystack.query import AutoQuery
from isodate import Duration, duration_isoformat, parse_duration
from modeltranslation.translator import translator, NotRegistered
from munigeo.api import (
    GeoModelSerializer, GeoModelAPIView, build_bbox_filter, srid_to_srs
)
from rest_framework import serializers, relations, viewsets, filters, generics
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.exceptions import ParseError

# this app
from events import utils
from events.custom_elasticsearch_search_backend import \
    CustomEsSearchQuerySet as SearchQuerySet
from events.models import (
    Place, Event, Keyword, Language, OpeningHoursSpecification, EventLink,
    Offer, DataSource, Organization
)
from events.translation import EventTranslationOptions


serializers_by_model = {}

all_views = []


def register_view(klass, name, base_name=None):
    entry = {'class': klass, 'name': name}
    if base_name is not None:
        entry['base_name'] = base_name
    all_views.append(entry)

    if klass.serializer_class and \
            hasattr(klass.serializer_class, 'Meta') and \
            hasattr(klass.serializer_class.Meta, 'model'):
        model = klass.serializer_class.Meta.model
        serializers_by_model[model] = klass.serializer_class


def urlquote_id(link):
    """
    URL quote link's id part, e.g.
    http://127.0.0.1:8000/v0.1/place/tprek:20879/
    -->
    http://127.0.0.1:8000/v0.1/place/tprek%3A20879/
    This is DRF backwards compatibility function, 2.x quoted id automatically.

    :param link: URL str
    :return: quoted URL str
    """
    if isinstance(link, str):
        parts = link.split('/')
        if len(parts) > 1 and ':' in parts[-2]:
            parts[-2] = urllib.parse.quote(parts[-2])
            link = '/'.join(parts)
    return link


def generate_id(namespace):
    t = time.time() * 1000
    postfix = base64.b32encode(struct.pack(">Q", int(t)).lstrip(b'\x00'))
    postfix = postfix.strip(b'=').lower().decode(encoding='UTF-8')
    return '{}:{}'.format(namespace, postfix)


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

    def use_pk_only_optimization(self):
        if self.is_expanded():
            return False
        else:
            return True

    def to_representation(self, obj):
        if isinstance(self.related_serializer, str):
            self.related_serializer = globals().get(self.related_serializer,
                                                    None)
        if self.is_expanded():
            return self.related_serializer(
                obj,
                hide_ld_context=self.hide_ld_context,
                context=self.context
            ).data
        link = super(JSONLDRelatedField, self).to_representation(obj)
        link = urlquote_id(link)
        return {
            '@id': link
        }

    def to_internal_value(self, value):
        if '@id' in value:
            return super(JSONLDRelatedField, self).to_internal_value(
                value['@id']
            )
        else:
            raise ValidationError(
                self.invalid_json_error % type(value).__name__)

    def is_expanded(self):
        return getattr(self, 'expanded', False)


class EnumChoiceField(serializers.Field):
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

    def to_representation(self, obj):
        if obj is None:
            return None
        val = 1
        return val  # FIXME
        # FIXME: and this may be broken:
        # return self.prefix + utils.get_value_from_tuple_list(self.choices,
        #                                                      obj, 1)

    def to_internal_value(self, data):
        val = utils.get_value_from_tuple_list(self.choices,
                                              self.prefix + str(data), 0)
        return val


class ISO8601DurationField(serializers.Field):

    def to_representation(self, obj):
        if obj:
            d = Duration(milliseconds=obj)
            return duration_isoformat(d)
        else:
            return None

    def to_internal_value(self, data):
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
        model = self.Meta.model
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

    def to_internal_value(self, data):
        """
        Convert complex translated json objects to flat format.
        E.g. json structure containing `name` key like this:
        {
            "name": {
                "fi": "musiikkiklubit",
                "sv": "musikklubbar",
                "en": "music clubs"
            },
            ...
        }
        Transforms this:
        {
            "name": "musiikkiklubit",
            "name_fi": "musiikkiklubit",
            "name_sv": "musikklubbar",
            "name_en": "music clubs"
            ...
        }

        :param data:
        :return:
        """
        lang = settings.LANGUAGES[0][0]
        for field_name in self.translated_fields:
            # FIXME: handle default lang like others!?
            lang = settings.LANGUAGES[0][0]  # Handle default lang
            if data.get(field_name, None) is None:
                continue
            values = data[field_name].copy()  # Save original values

            key = "%s_%s" % (field_name, lang)
            val = data[field_name].get(lang)
            if val:
                values[key] = val  # field_name_LANG
                values[field_name] = val  # field_name
            if lang in values:
                del values[lang]  # Remove original key LANG
            for lang in [x[0] for x in settings.LANGUAGES[1:]]:
                key = "%s_%s" % (field_name, lang)
                val = data[field_name].get(lang)
                if val:
                    values[key] = val  # field_name_LANG
                    values[field_name] = val  # field_name
                if lang in values:
                    del values[lang]  # Remove original key LANG
            data.update(values)
            del data[field_name]  # Remove original field_name from data
        return data

    def to_representation(self, obj):
        ret = super(TranslatedModelSerializer, self).to_representation(obj)
        if obj is None:
            return ret
        return self.translated_fields_to_representation(obj, ret)

    def translated_fields_to_representation(self, obj, ret):
        for field_name in self.translated_fields:
            d = {}
            default_lang = settings.LANGUAGES[0][0]
            d[default_lang] = getattr(obj, field_name)
            for lang in [x[0] for x in settings.LANGUAGES[1:]]:
                key = "%s_%s" % (field_name, lang)
                val = getattr(obj, key, None)
                if val is None:
                    continue
                d[lang] = val

            # If no text provided, leave the field as null
            for key, val in d.items():
                if val is not None:
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

    # def __init__(self, instance=None, data=None, files=None,
    #              context=None, partial=False, many=None,
    #              allow_add_remove=False, hide_ld_context=False, **kwargs):
    #     super(LinkedEventsSerializer, self).__init__(
    #         instance=instance, context=context, **kwargs)
    def __init__(self, *args, **kwargs):
        hide_ld_context = kwargs.pop('hide_ld_context', False)
        super(LinkedEventsSerializer, self).__init__(*args, **kwargs)
        allow_add_remove = kwargs.pop('allow_add_remove', False)
        partial = kwargs.pop('partial', False)
        files = kwargs.pop('files', None)
        many = kwargs.pop('many', None)

        if 'created_by' in self.fields:
            del self.fields['created_by']
        if 'modified_by' in self.fields:
            del self.fields['modified_by']

        context = kwargs.get('context', None)

        if context is not None:
            include_fields = context.get('include', [])
            for field_name in include_fields:
                if field_name not in self.fields:
                    continue
                field = self.fields[field_name]
                if isinstance(field, relations.ManyRelatedField):
                    field = field.child_relation
                if not isinstance(field, JSONLDRelatedField):
                    continue
                field.expanded = True

        self.hide_ld_context = hide_ld_context

        self.disable_camelcase = True
        if 'request' in self.context:
            request = self.context['request']
            if 'disable_camelcase' in request.query_params:
                self.disable_camelcase = True

    def to_representation(self, obj):
        """
        Before sending to renderer there's a need to do additional work on
        to-be-JSON dictionary data:
            1. Add @context, @type and @id fields
            2. Convert field names to camelCase
        Renderer is the right place for this but now loop is done just once.
        Reversal conversion is done in parser.
        """
        ret = super(LinkedEventsSerializer, self).to_representation(obj)
        if 'id' in ret and 'request' in self.context:
            try:
                ret['@id'] = reverse(self.view_name,
                                     kwargs={u'pk': ret['id']},
                                     request=self.context['request'])
            except NoReverseMatch:
                ret['@id'] = str(ret['id'])
            ret['@id'] = urlquote_id(ret['@id'])

        # Context is hidden if:
        # 1) hide_ld_context is set to True
        #   2) self.object is None, e.g. we are in the list of stuff
        if not self.hide_ld_context and self.instance is not None:
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


def _clean_qp(query_params):
    """
    Strip 'event.' prefix from all query params.
    :rtype : QueryDict
    :param query_params: dict self.request.query_params
    :return: QueryDict query_params
    """
    query_params = query_params.copy()  # do not alter original dict
    nspace = 'event.'
    for key in query_params.keys():
        if key.startswith(nspace):
            new_key = key[len(nspace):]
            # .pop() returns a list(?), don't use
            # query_params[new_key] = query_params.pop(key)
            query_params[new_key] = query_params[key]
            del query_params[key]
    return query_params


class KeywordSerializer(LinkedEventsSerializer):
    view_name = 'keyword-detail'

    class Meta:
        model = Keyword


class KeywordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Keyword.objects.all()
    serializer_class = KeywordSerializer

    def get_queryset(self):
        """
        Return Keyword queryset. If request has parameter show_all_keywords=1
        all Keywords are returned, otherwise only which have events.
        Additional query parameters:
        event.data_source
        event.start
        event.end
        """
        queryset = Keyword.objects.all()
        if self.request.query_params.get('show_all_keywords'):
            # Limit by data_source anyway, if it is set
            data_source = self.request.query_params.get('data_source')
            if data_source:
                data_source = data_source.lower()
                queryset = queryset.filter(data_source=data_source)
        else:
            events = Event.objects.all()
            params = _clean_qp(self.request.query_params)
            events = _filter_event_queryset(events, params)
            keyword_ids = events.values_list('keywords',
                                             flat=True).distinct().order_by()
            queryset = queryset.filter(id__in=keyword_ids)
        # Optionally filter keywords by filter parameter,
        # can be used e.g. with typeahead.js
        val = self.request.query_params.get('filter')
        if val:
            queryset = queryset.filter(name__startswith=val)
        return queryset

register_view(KeywordViewSet, 'keyword')


class PlaceSerializer(LinkedEventsSerializer, GeoModelSerializer):
    view_name = 'place-detail'

    class Meta:
        model = Place


class PlaceViewSet(GeoModelAPIView, viewsets.ReadOnlyModelViewSet):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer

    def get_queryset(self):
        """
        Return Place queryset. If request has parameter show_all_places=1
        all Places are returned, otherwise only which have events.
        Additional query parameters:
        event.data_source
        event.start
        event.end
        """
        queryset = Place.objects.all()
        if self.request.query_params.get('show_all_places'):
            pass
        else:
            events = Event.objects.all()
            params = _clean_qp(self.request.query_params)
            events = _filter_event_queryset(events, params)
            location_ids = events.values_list('location_id',
                                              flat=True).distinct().order_by()
            queryset = queryset.filter(id__in=location_ids)
        return queryset

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
    def to_representation(self, obj):
        ret = super(EventLinkSerializer, self).to_representation(obj)
        if not ret['name']:
            ret['name'] = None
        return ret

    class Meta:
        model = EventLink
        exclude = ['id', 'event']


class OfferSerializer(TranslatedModelSerializer):
    class Meta:
        model = Offer
        exclude = ['id', 'event']


def parse_id_from_uri(uri):
    """
    Parse id part from @id uri like
    'http://127.0.0.1:8000/v0.1/event/matko%3A666/' -> 'matko:666'
    :param uri: str
    :return: str id
    """
    assert(uri.startswith('http'))
    path = urllib.parse.urlparse(uri).path
    _id = path.rstrip('/').split('/')[-1]
    _id = urllib.parse.unquote(_id)
    return _id


class EventSerializer(LinkedEventsSerializer, GeoModelAPIView):
    location = JSONLDRelatedField(serializer=PlaceSerializer, required=False,
                                  view_name='place-detail', read_only=True)
    # provider = OrganizationSerializer(hide_ld_context=True)
    keywords = JSONLDRelatedField(serializer=KeywordSerializer, many=True,
                                  required=False,
                                  view_name='keyword-detail', read_only=True)
    super_event = JSONLDRelatedField(required=False, view_name='event-detail',
                                     read_only=True)
    event_status = EnumChoiceField(Event.STATUSES)
    external_links = EventLinkSerializer(many=True)
    offers = OfferSerializer(many=True)
    sub_events = JSONLDRelatedField(serializer='EventSerializer',
                                    required=False, view_name='event-detail',
                                    many=True, read_only=True)

    view_name = 'event-detail'

    def __init__(self, *args, skip_empties=False, skip_fields=set(), **kwargs):
        super(EventSerializer, self).__init__(*args, **kwargs)
        # The following can be used when serializing when
        # testing and debugging.
        self.skip_empties = skip_empties
        self.skip_fields = skip_fields

    def create(self, validated_data):

        if 'id' in validated_data:
            err = "Do not send 'id' when POSTing a new Event (got id='{}')"
            raise ParseError(err.format(validated_data['id']))

        data_source = validated_data.get('data_source')
        data_source_id = data_source.id if data_source else 'linkedevents'

        keywords = validated_data.pop('keywords')
        offers = validated_data.pop('offers', [])
        links = validated_data.pop('external_links', [])

        validated_data['id'] = generate_id(data_source_id)

        e = Event.objects.create(**validated_data)
        e.keywords.add(*keywords)

        # create offers (should be validated already in `validate` method)
        for offer in offers:
            off_ser = OfferSerializer(data=offer)
            assert(off_ser.is_valid())
            obj = Offer(event=e, **off_ser.validated_data)
            obj.save()

        # create ext links (should be validated already in `validate` method)
        for link in links:
            link_ser = EventLinkSerializer(data=link)
            assert(link_ser.is_valid())
            obj = EventLink(event=e, **link_ser.validated_data)
            obj.save()

        # silly hack to keep the redundant (?) `headline` field in sync with
        # the `name` field... if `headline` is not set, we make it match
        # `name`.
        #
        # TODO: review with actual end users
        languages = [x[0] for x in settings.LANGUAGES]
        for lang in languages:
            HEADLINE, NAME =  'headline_%s' % lang, 'name_%s' % lang
            if not getattr(e, HEADLINE, None):
                setattr(e, HEADLINE, getattr(e, NAME))

        return e

    def update(self, instance, validated_data):
        languages = [x[0] for x in settings.LANGUAGES]
        update_fields = [
            'start_time', 'end_time',
        ]

        for field in EventTranslationOptions.fields:
            for lang in languages:
                update_fields.append(field + '_' + lang)

        # silly hack to keep the redundant (?) `headline` field in sync with
        # the `name` field... if `name` is changed, we also update `headline`
        # to match `name`.
        #
        # TODO: review with actual end users
        for lang in languages:
            HEADLINE, NAME = 'headline_%s' % lang, 'name_%s' % lang
            a, b = (
                getattr(instance, NAME, None),
                validated_data.get(NAME, None)
            )
            if a != b:
                validated_data[HEADLINE] = validated_data.get(NAME, None)

        for field in update_fields:
            orig_value = getattr(instance, field)
            new_value = validated_data.get(field, orig_value)
            setattr(instance, field, new_value)

        if instance.end_time:
            instance.has_end_time = True


        instance.save()

        # update offers
        # NOTE this currently deletes all the existing and inserts new ones
        # TODO review and decide on whether this should be done differently
        if 'offers' in validated_data:
            instance.offers.all().delete()
            for offer in validated_data.get('offers', []):
                off_ser = OfferSerializer(data=offer)
                assert(off_ser.is_valid())
                obj = Offer(event=instance, **off_ser.validated_data)
                obj.save()

        # create ext links
        # NOTE this currently deletes all the existing and inserts new ones
        # TODO review and decide on whether this should be done differently
        if 'external_links' in validated_data:
            instance.external_links.all().delete()
            for link in validated_data.get('external_links', []):
                link_ser = EventLinkSerializer(data=link)
                assert(link_ser.is_valid())
                obj = EventLink(event=instance, **link_ser.validated_data)
                obj.save()

        return instance

    def validate(self, attrs):

        # validate offers
        for offer in attrs.get('offers', []):
            off_ser = OfferSerializer(data=offer)
            if not off_ser.is_valid():
                raise ValidationError('Invalid offer [%s].' % offer)

        # validate external links
        for link in attrs.get('external_links', []):
            link_ser = EventLinkSerializer(data=link)
            if not link_ser.is_valid():
                raise ValidationError('Invalid external link [%s].' % link)
        return attrs

    def to_internal_value(self, data):
        # TODO: common stuff to LinkedEventsSerializer
        data = super(EventSerializer, self).to_internal_value(data)
        self._parse_keywords(data)
        self._parse_location(data)
        self._parse_publisher(data)
        self._delete_obsolete_keys(data)

        # time parser raises parse error if start_time is not valid
        start_time = data.get('start_time', None)
        if start_time:
            if isinstance(start_time, str):
                data['start_time'] = parse_time(start_time, True)

        end_time = data.get('end_time', '')
        if end_time and isinstance(end_time, str):
            data['end_time'] = parse_time(end_time, False)

        # TODO: check this
        data_source_id = data.get('data_source')
        if data_source_id:
            # TODO: error handling and raise ParseError
            data['data_source'] = DataSource.objects.get(id=data_source_id)

        event_status = data.get('event_status')  # e.g. EventScheduled
        if event_status:
            data['event_status'] = 1  # FIXME: really

        foobar = data.copy()
        for k in data.keys():
            if data[k] is None:
                del foobar[k]
            else:
                pass

        return foobar

    def to_representation(self, obj):
        ret = super(EventSerializer, self).to_representation(obj)

        if 'start_time' in ret and not obj.has_start_time:
            # Return only the date part
            ret['start_time'] = obj.start_time.astimezone(LOCAL_TZ)\
                .strftime('%Y-%m-%d')

        if 'end_time' in ret and not obj.has_end_time:
            # If we're storing only the date part, do not pretend we have the
            # exact time.
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

    def _delete_obsolete_keys(self, data):
        for k in [
            'sub_events', 'super_event',
            '@context', '@type', '@id',
            'last_modified_time', 'created_time', 'date_published'
        ]:
            if k in data:
                del data[k]

    def _parse_keywords(self, data):
        """
        Replace list of keyword dicts in data with a list of Keyword objects
        """
        new_kw = []

        for kw in data.get('keywords', []):

            if '@id' in kw:
                kw_id = parse_id_from_uri(kw['@id'])

                try:
                    keyword = Keyword.objects.get(id=kw_id)
                except Keyword.DoesNotExist:
                    err = 'Keyword with id {} does not exist'
                    raise ParseError(err.format(kw_id))

                new_kw.append(keyword)

        data['keywords'] = new_kw

    def _parse_location(self, data):
        """
        Replace location id dict in data with a Place object
        """
        location = data.get('location')
        if location and '@id' in location:
            location_id = parse_id_from_uri(location['@id'])
            try:
                data['location'] = Place.objects.get(id=location_id)
            except Place.DoesNotExist:
                err = 'Place with id {} does not exist'
                raise ParseError(err.format(location_id))

    def _parse_publisher(self, data):
        organization_id = data.get('publisher')
        if organization_id:
            # TODO: error handling and raise ParseError
            data['publisher'] = Organization.objects.get(id=organization_id)


def parse_time(time_str, is_start):
    time_str = time_str.strip()
    # Handle dates first. Assume dates are given in local timezone.
    # FIXME: What if there's no local timezone?
    try:
        dt = datetime.strptime(time_str, '%Y-%m-%d')
        dt = LOCAL_TZ.localize(dt)
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

            # by default, if no timezone is set, use the local timezone
            if dt.tzinfo is None:
                dt = LOCAL_TZ.localize(dt)

        except (TypeError, ValueError):
            err = 'time in invalid format (try ISO 8601 or yyyy-mm-dd)'
            raise ParseError(err)
    return dt


# class JSONAPIViewSet(viewsets.ReadOnlyModelViewSet):
class JSONAPIViewSet(viewsets.ModelViewSet):
    def initial(self, request, *args, **kwargs):
        ret = super(JSONAPIViewSet, self).initial(request, *args, **kwargs)
        self.srs = srid_to_srs(self.request.query_params.get('srid', None))
        return ret

    def get_serializer_context(self):
        context = super(JSONAPIViewSet, self).get_serializer_context()

        include = self.request.query_params.get('include', '')
        context['include'] = [x.strip() for x in include.split(',') if x]
        context['srs'] = self.srs

        return context


class LinkedEventsOrderingFilter(filters.OrderingFilter):
    ordering_param = 'sort'


class EventOrderingFilter(LinkedEventsOrderingFilter):
    def filter_queryset(self, request, queryset, view):
        queryset = super(EventOrderingFilter, self).filter_queryset(
            request, queryset, view
        )
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            ordering = []
        if 'days_left' in [x.lstrip('-') for x in ordering]:
            queryset = queryset.extra(select={
                'days_left': 'date_part(\'day\', end_time - start_time)'
            })
        return queryset


def parse_duration(duration):
    m = re.match(r'(\d+)\s*(d|h|m|s)?$', duration.strip().lower())
    if not m:
        raise ParseError("Invalid duration supplied. Try '1d' or '2h'.")
    val, unit = m.groups()
    if not unit:
        unit = 's'

    if unit == 'm':
        mul = 60
    elif unit == 'h':
        mul = 3600
    elif unit == 'd':
        mul = 24 * 3600

    return int(val) * mul


def _filter_event_queryset(queryset, params, srs=None):
    """
    Filter events queryset by params
    (e.g. self.request.query_params in EventViewSet)
    """
    # Filter by string (case insensitive). This searches from all fields
    # which are marked translatable in translation.py
    val = params.get('text', None)
    if val:
        val = val.lower()
        # Free string search from all translated fields
        fields = EventTranslationOptions.fields
        # and these languages
        languages = [x[0] for x in settings.LANGUAGES]
        qset = Q()
        for field in fields:
            for lang in languages:
                kwarg = {field + '_' + lang + '__icontains': val}
                qset |= Q(**kwarg)
        queryset = queryset.filter(qset)

    val = params.get('last_modified_since', None)
    # This should be in format which dateutil.parser recognizes, e.g.
    # 2014-10-29T12:00:00Z == 2014-10-29T12:00:00+0000 (UTC time)
    # or 2014-10-29T12:00:00+0200 (local time)
    if val:
        dt = parse_time(val, is_start=False)
        queryset = queryset.filter(Q(last_modified_time__gte=dt))

    val = params.get('start', None)
    if val:
        dt = parse_time(val, is_start=True)
        queryset = queryset.filter(Q(end_time__gt=dt) | Q(start_time__gte=dt))

    val = params.get('end', None)
    if val:
        dt = parse_time(val, is_start=False)
        queryset = queryset.filter(Q(end_time__lt=dt) | Q(start_time__lte=dt))

    val = params.get('bbox', None)
    if val:
        bbox_filter = build_bbox_filter(srs, val, 'position')
        places = Place.geo_objects.filter(**bbox_filter)
        queryset = queryset.filter(location__in=places)

    val = params.get('data_source', None)
    if val:
        queryset = queryset.filter(data_source=val)

    val = params.get('publisher', None)
    if val:
        queryset = queryset.filter(publisher=val)

    # Filter by location id, multiple ids separated by comma
    val = params.get('location', None)
    if val:
        val = val.split(',')
        queryset = queryset.filter(location_id__in=val)

    # Filter by keyword id, multiple ids separated by comma
    val = params.get('keyword', None)
    if val:
        val = val.split(',')
        queryset = queryset.filter(keywords__pk__in=val)

    # Filter only super or sub events if recurring has value
    val = params.get('recurring', None)
    if val:
        val = val.lower()
        if val == 'super':
            queryset = queryset.filter(is_recurring_super=True)
        elif val == 'sub':
            queryset = queryset.filter(is_recurring_super=False)

    val = params.get('max_duration', None)
    if val:
        dur = parse_duration(val)
        cond = 'end_time - start_time <= %s :: interval'
        queryset = queryset.extra(where=[cond], params=[str(dur)])

    val = params.get('min_duration', None)
    if val:
        dur = parse_duration(val)
        cond = 'end_time - start_time >= %s :: interval'
        queryset = queryset.extra(where=[cond], params=[str(dur)])

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

        if 'show_all' not in self.request.query_params:
            queryset = queryset.filter(
                Q(event_status=Event.SCHEDULED)
            )
        queryset = _filter_event_queryset(queryset, self.request.query_params,
                                          srs=self.srs)
        return queryset


register_view(EventViewSet, 'event')


class SearchSerializer(serializers.Serializer):
    def to_representation(self, search_result):
        model = search_result.model
        assert model in serializers_by_model, \
            "Serializer for %s not found" % model
        ser_class = serializers_by_model[model]
        data = ser_class(search_result.object, context=self.context).data
        data['object_type'] = model._meta.model_name
        data['score'] = search_result.score
        return data


DATE_DECAY_SCALE = '30d'


class SearchViewSet(GeoModelAPIView, viewsets.ViewSetMixin,
                    generics.ListAPIView):
    serializer_class = SearchSerializer

    def list(self, request, *args, **kwargs):
        languages = [x[0] for x in settings.LANGUAGES]

        # If the incoming language is not specified, go with the default.
        self.lang_code = request.query_params.get('language', languages[0])
        if self.lang_code not in languages:
            err = 'Invalid language supplied. Supported languages: %s'
            raise ParseError(err % ','.join(languages))

        input_val = request.query_params.get('input', '').strip()
        q_val = request.query_params.get('q', '').strip()
        if not input_val and not q_val:
            err = (
                "Supply search terms with 'q=' or autocomplete entry "
                "with 'input='"
            )
            raise ParseError(err)
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
                        'scale': DATE_DECAY_SCALE
                    }
                }
            })
        else:
            queryset = queryset.filter(text=AutoQuery(q_val))

        self.object_list = queryset.load_all()

        page = self.paginate_queryset(self.object_list)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(self.object_list, many=True)
        resp = Response(serializer.data)

        translation.activate(old_language)

        return resp


register_view(SearchViewSet, 'search', base_name='search')
