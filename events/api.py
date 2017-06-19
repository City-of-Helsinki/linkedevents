# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# python
import base64
import re
import struct
import time
import urllib.parse
from datetime import datetime, timedelta
from dateutil.parser import parse as dateutil_parse

# django and drf
from django.db.transaction import atomic
from django.http import Http404
from django.utils import translation
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.utils import IntegrityError
from django.conf import settings
from django.core.urlresolvers import NoReverseMatch
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.utils.encoding import force_text
from rest_framework import (
    serializers, relations, viewsets, mixins, filters, generics, status, permissions
)
from rest_framework.settings import api_settings
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.exceptions import ParseError, PermissionDenied as DRFPermissionDenied
from rest_framework.views import get_view_name as original_get_view_name


# 3rd party
from isodate import Duration, duration_isoformat, parse_duration
from modeltranslation.translator import translator, NotRegistered
from haystack.query import AutoQuery
from munigeo.api import (
    GeoModelSerializer, GeoModelAPIView, build_bbox_filter, srid_to_srs
)
from munigeo.models import AdministrativeDivision
from rest_framework_bulk import BulkListSerializer, BulkModelViewSet
import pytz
import bleach
import django_filters

# events
from events import utils
from events.api_pagination import LargeResultsSetPagination
from events.auth import ApiKeyAuth, ApiKeyUser
from events.custom_elasticsearch_search_backend import (
    CustomEsSearchQuerySet as SearchQuerySet
)
from events.models import (
    Place, Event, Keyword, KeywordSet, Language, OpeningHoursSpecification, EventLink,
    Offer, DataSource, Organization, Image, PublicationStatus, PUBLICATION_STATUSES, License
)
from events.translation import EventTranslationOptions
from helevents.models import User


def get_view_name(cls, suffix=None):
    if cls.__name__ == 'APIRootView':
        return 'Linked Events'
    return original_get_view_name(cls, suffix)


viewset_classes_by_model = {}

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
        viewset_classes_by_model[model] = klass

def get_serializer_for_model(model, version='v1'):
    Viewset = viewset_classes_by_model.get(model)
    if Viewset is None: return None
    serializer = None
    if hasattr(Viewset, 'get_serializer_class_for_version'):
        serializer = Viewset.get_serializer_class_for_version(version)
    elif hasattr(Viewset, 'serializer_class'):
        serializer = Viewset.serializer_class
    return serializer


def generate_id(namespace):
    t = time.time() * 1000
    postfix = base64.b32encode(struct.pack(">Q", int(t)).lstrip(b'\x00'))
    postfix = postfix.strip(b'=').lower().decode(encoding='UTF-8')
    return '{}:{}'.format(namespace, postfix)

def parse_id_from_uri(uri):
    """
    Parse id part from @id uri like
    'http://127.0.0.1:8000/v0.1/event/matko%3A666/' -> 'matko:666'
    :param uri: str
    :return: str id
    """
    if not uri.startswith('http'):
        return uri
    path = urllib.parse.urlparse(uri).path
    _id = path.rstrip('/').split('/')[-1]
    _id = urllib.parse.unquote(_id)
    return _id

def perform_id_magic_for(data):
    if 'id' in data:
        err = "Do not send 'id' when POSTing a new Event (got id='{}')"
        raise ParseError(err.format(data['id']))
    data['id'] = generate_id(data['data_source'])
    return data

def get_authenticated_data_source_and_publisher(request):
    # api_key takes precedence over user
    if isinstance(request.auth, ApiKeyAuth):
        data_source = request.auth.get_authenticated_data_source()
        publisher = data_source.owner
        if not publisher:
            raise PermissionDenied(_("Data source doesn't belong to any organization"))
    else:
        # objects created by api are marked coming from the system data source unless api_key is provided
        # we must optionally create the system data source here, as the settings may have changed at any time
        data_source, created = DataSource.objects.get_or_create(id=settings.SYSTEM_DATA_SOURCE_ID)
        # user organization is used unless api_key is provided
        user = request.user
        if isinstance(user, User):
            publisher = user.get_default_organization()
        else:
            publisher = None
    return data_source, publisher


class JSONLDRelatedField(relations.HyperlinkedRelatedField):
    """
    Support of showing and saving of expanded JSON nesting or just a resource
    URL.
    Serializing is controlled by query string param 'expand', deserialization
    by format of JSON given.

    Default serializing is expand=false.
    """

    invalid_json_error = _('Incorrect JSON. Expected JSON, received %s.')

    def __init__(self, *args, **kwargs):
        self.related_serializer = kwargs.pop('serializer', None)
        self.hide_ld_context = kwargs.pop('hide_ld_context', False)
        self.expanded = kwargs.pop('expanded', False)
        super(JSONLDRelatedField, self).__init__(*args, **kwargs)

    def use_pk_only_optimization(self):
        if self.is_expanded():
            return False
        else:
            return True

    def to_representation(self, obj):
        if isinstance(self.related_serializer, str):
            self.related_serializer = globals().get(self.related_serializer, None)
        if self.is_expanded():
            return self.related_serializer(obj, hide_ld_context=self.hide_ld_context,
                                           context=self.context).data
        link = super(JSONLDRelatedField, self).to_representation(obj)
        if link == None:
            return None
        return {
            '@id': link
        }

    def to_internal_value(self, value):
        # TODO: JA If @id is missing, this will complain just about value not being JSON
        if not isinstance(value, dict) or '@id' not in value:
            raise ValidationError(self.invalid_json_error % type(value).__name__)

        url = value['@id']
        if not url:
            if self.required:
                raise ValidationError(_('This field is required.'))
            return None

        return super().to_internal_value(urllib.parse.unquote(url))

    def is_expanded(self):
        return getattr(self, 'expanded', False)


class EnumChoiceField(serializers.Field):
    """
    Database value of tinyint is converted to and from a string representation
    of choice field.

    TODO: Find if there's standardized way to render Schema.org enumeration
    instances in JSON-LD.
    """

    def __init__(self, choices, prefix='', **kwargs):
        self.choices = choices
        self.prefix = prefix
        super(EnumChoiceField, self).__init__(**kwargs)

    def to_representation(self, obj):
        if obj is None:
            return None
        return self.prefix + utils.get_value_from_tuple_list(self.choices,
                                                             obj, 1)

    def to_internal_value(self, data):
        value = utils.get_value_from_tuple_list(self.choices,
                                               self.prefix + str(data), 0)
        if value is None:
            raise ParseError(_("Invalid value in event_status"))
        return value


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

    def to_representation(self, obj):
        ret = super(TranslatedModelSerializer, self).to_representation(obj)
        if obj is None:
            return ret
        return self.translated_fields_to_representation(obj, ret)

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

        extra_fields = {}  # will contain the transformation result
        for field_name in self.translated_fields:
            obj = data.get(field_name, None)  # { "fi": "musiikkiklubit", "sv": ... }
            if not obj:
                continue
            if not isinstance(obj, dict):
                raise ValidationError({field_name: 'This field is a translated field. Instead of a string,'
                                                   ' you must supply an object with strings corresponding'
                                                   ' to desired language ids.'})
            for language in (lang[0] for lang in settings.LANGUAGES if lang[0] in obj):
                value = obj[language]  # "musiikkiklubit"
                if language == settings.LANGUAGES[0][0]:  # default language
                    extra_fields[field_name] = value  # { "name": "musiikkiklubit" }
                extra_fields['{}_{}'.format(field_name, language)] = value  # { "name_fi": "musiikkiklubit" }
            del data[field_name]  # delete original translated fields

        # handle other than translated fields
        data = super().to_internal_value(data)

        # add translated fields to the final result
        data.update(extra_fields)

        return data

    def translated_fields_to_representation(self, obj, ret):
        for field_name in self.translated_fields:
            d = {}
            for lang in [x[0] for x in settings.LANGUAGES]:
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
    system_generated_fields = ('created_time', 'last_modified_time', 'created_by', 'last_modified_by')
    non_visible_fields = ('created_by', 'last_modified_by')

    def __init__(self, instance=None, files=None,
                 context=None, partial=False, many=None, skip_fields=set(),
                 allow_add_remove=False, hide_ld_context=False, **kwargs):
        super(LinkedEventsSerializer, self).__init__(
            instance=instance, context=context, **kwargs)
        for field in self.non_visible_fields:
            if field in self.fields:
                del self.fields[field]
        self.skip_fields = skip_fields

        if context is not None:
            include_fields = context.get('include', [])
            for field_name in include_fields:
                if not field_name in self.fields:
                    continue
                field = self.fields[field_name]
                if isinstance(field, relations.ManyRelatedField):
                    field = field.child_relation
                if not isinstance(field, JSONLDRelatedField):
                    continue
                field.expanded = True
            self.skip_fields |= context.get('skip_fields', set())

        self.hide_ld_context = hide_ld_context

        self.disable_camelcase = True
        if self.context and 'request' in self.context:
            request = self.context['request']
            if 'disable_camelcase' in request.query_params:
                self.disable_camelcase = True

        # for post and put methods, user information is needed to restrict permissions at validate
        if context is None:
            return
        self.method = self.context['request'].method
        self.user = self.context['request'].user
        if self.method in permissions.SAFE_METHODS:
            return
        self.data_source, self.publisher = get_authenticated_data_source_and_publisher(request)
        if not self.publisher:
            raise PermissionDenied(_("User doesn't belong to any organization"))


    def to_internal_value(self, data):
        for field in self.system_generated_fields:
            if field in data:
                del data[field]
        data = super().to_internal_value(data)
        return data

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
        if self.context['request'].version == 'v0.1':
            return ret
        for field in self.skip_fields:
            if field in ret:
                del ret[field]
        return ret

    def validate_data_source(self, value):
        if value:
            if value != self.data_source:
                # the event might be from another data source by the same organization, and we are only editing it
                if self.instance:
                    if self.publisher.owned_systems.filter(id=value).exists():
                        return value
                raise serializers.ValidationError(
                    {'data_source': _("Setting data_source to %(given)s " +
                             " is not allowed for your organization. The data_source"
                             " must be left blank or set to %(required)s ") %
                           {'given': str(value), 'required': self.data_source}})
        return value

    def validate_publisher(self, value):
        if value:
            if value != self.publisher:
                raise serializers.ValidationError(
                    {'publisher': _("Setting publisher to %(given)s " +
                                    " is not allowed for your organization. The publisher" +
                                    " must be left blank or set to %(required)s ") %
                                  {'given': str(value), 'required': self.publisher}})
        return value

    def validate(self, data):
        if 'name' in self.translated_fields:
            name_exists = False
            languages = [x[0] for x in settings.LANGUAGES]
            for language in languages:
                if 'name_%s' % language in data:
                    name_exists = True
                    break
        else:
            name_exists = 'name' in data
        if not name_exists:
            raise serializers.ValidationError({'name': _('The name must be specified.')})
        super().validate(data)
        return data

    def create(self, validated_data):
        if 'data_source' not in validated_data:
            validated_data['data_source'] = self.data_source
        if 'publisher' not in validated_data:
            validated_data['publisher'] = self.publisher
        # no django user exists for the api key
        if isinstance(self.user, ApiKeyUser):
            self.user = None
        validated_data['created_by'] = self.user
        validated_data['last_modified_by'] = self.user
        try:
            instance = super().create(validated_data)
        except IntegrityError as error:
            if 'duplicate' and 'pkey' in str(error):
                raise serializers.ValidationError({'id':_("An object with given id already exists.")})
            else:
                raise error
        return instance

    def update(self, instance, validated_data):
        if isinstance(self.user, ApiKeyUser):
            # allow updating only if the api key matches instance data source
            self.user = None
            if not instance.data_source == self.data_source:
                raise PermissionDenied()
        else:
            # without api key, the user will have to be admin
            if not instance.is_user_editable() or not instance.is_admin(self.user):
                raise PermissionDenied()
        validated_data['last_modified_by'] = self.user

        if 'id' in validated_data:
            if instance.id != validated_data['id']:
                raise serializers.ValidationError({'id':_("You may not change the id of an existing object.")})
        super().update(instance, validated_data)
        return instance


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
    alt_labels = serializers.SlugRelatedField(slug_field='name', read_only=True, many=True)

    class Meta:
        model = Keyword
        exclude = ('n_events_changed',)


class KeywordRetrieveViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Keyword.objects.all()
    serializer_class = KeywordSerializer


class KeywordListViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Keyword.objects.all()
    serializer_class = KeywordSerializer
    filter_backends = (filters.OrderingFilter,)
    ordering_fields = ('n_events', 'id', 'name', 'data_source')
    ordering = ('-data_source', '-n_events',)

    def get_queryset(self):
        """
        Return Keyword queryset.

        If the request has no filter parameters, we only return keywords that meet the following criteria:
        -the keyword has events
        -the keyword is not deprecated

        Supported keyword filtering parameters:
        data_source (only keywords with the given data sources are included)
        filter (only keywords containing the specified string are included)
        show_all_keywords (keywords without events are included)
        show_deprecated (deprecated keywords are included)
        """
        queryset = Keyword.objects.all()
        data_source = self.request.query_params.get('data_source')
        # Filter by data source, multiple sources separated by comma
        if data_source:
            data_source = data_source.lower().split(',')
            queryset = queryset.filter(data_source__in=data_source)
        if not self.request.query_params.get('show_all_keywords'):
            queryset = queryset.filter(n_events__gt=0)
        if not self.request.query_params.get('show_deprecated'):
            queryset = queryset.filter(deprecated=False)

        # Optionally filter keywords by filter parameter,
        # can be used e.g. with typeahead.js
        val = self.request.query_params.get('text') or self.request.query_params.get('filter')
        if val:
            queryset = queryset.filter(name__icontains=val)
        return queryset


register_view(KeywordRetrieveViewSet, 'keyword')
register_view(KeywordListViewSet, 'keyword')


class KeywordSetSerializer(LinkedEventsSerializer):
    view_name = 'keywordset-detail'
    keywords = JSONLDRelatedField(
        serializer=KeywordSerializer, many=True, required=True, allow_empty=False,
        view_name='keyword-detail', queryset=Keyword.objects.all())
    usage = EnumChoiceField(KeywordSet.USAGES)

    class Meta:
        model = KeywordSet
        fields = '__all__'


class JSONAPIViewSet(viewsets.ReadOnlyModelViewSet):
    def initial(self, request, *args, **kwargs):
        ret = super(JSONAPIViewSet, self).initial(request, *args, **kwargs)
        self.srs = srid_to_srs(self.request.query_params.get('srid', None))
        return ret

    def get_serializer_context(self):
        context = super(JSONAPIViewSet, self).get_serializer_context()

        include = self.request.query_params.get('include', '')
        context['include'] = [x.strip() for x in include.split(',') if x]
        context['srs'] = self.srs
        context.setdefault('skip_fields', set()).add('origin_id')
        return context


class KeywordSetViewSet(JSONAPIViewSet):
    queryset = KeywordSet.objects.all()
    serializer_class = KeywordSetSerializer

register_view(KeywordSetViewSet, 'keyword_set')


class DivisionSerializer(TranslatedModelSerializer):
    type = serializers.SlugRelatedField(slug_field='type', read_only=True)
    municipality = serializers.SlugRelatedField(slug_field='name', read_only=True)

    class Meta:
        model = AdministrativeDivision
        fields = ('type', 'name', 'ocd_id', 'municipality')


def filter_division(queryset, name, value):
    """
    Allows division filtering by both division name and more specific ocd id (identified by colon in the parameter)

    Depending on the deployment location, offers simpler filtering by appending
    country and municipality information to ocd ids.

    Examples:
        /event/?division=kamppi
        will match any and all divisions with the name Kamppi, regardless of their type.

        /event/?division=ocd-division/country:fi/kunta:helsinki/osa-alue:kamppi
        /event/?division=ocd-division/country:fi/kunta:helsinki/suurpiiri:kamppi
        will match different division types with the otherwise identical id kamppi.

        /event/?division=osa-alue:kamppi
        /event/?division=suurpiiri:kamppi
        will match different division types with the id kamppi, if correct country and municipality information is
        present in settings.

        /event/?division=helsinki
        will match any and all divisions with the name Helsinki, regardless of their type.

        /event/?division=ocd-division/country:fi/kunta:helsinki
        will match the Helsinki municipality.

        /event/?division=kunta:helsinki
        will match the Helsinki municipality, if correct country information is present in settings.

    """

    ocd_ids = []
    names = []
    for item in value:
        if ':' in item:
            # we have a munigeo division
            if hasattr(settings, 'MUNIGEO_MUNI') and hasattr(settings, 'MUNIGEO_COUNTRY'):
                # append ocd path if we have deployment information
                if not item.startswith('ocd-division'):
                    if not item.startswith('country'):
                        if not item.startswith('kunta'):
                            item = settings.MUNIGEO_MUNI + '/' + item
                        item = settings.MUNIGEO_COUNTRY + '/' + item
                    item = 'ocd-division/' + item
            ocd_ids.append(item)
        else:
            # we assume human name
            names.append(item.title())
    return (queryset.filter(**{name + '__ocd_id__in': ocd_ids})|
            queryset.filter(**{name + '__name__in': names})).distinct()


class PlaceSerializer(LinkedEventsSerializer, GeoModelSerializer):
    view_name = 'place-detail'
    divisions = DivisionSerializer(many=True, read_only=True)

    class Meta:
        model = Place
        exclude = ('n_events_changed',)


class PlaceFilter(filters.FilterSet):
    division = django_filters.Filter(name='divisions', lookup_type='in',
                                     widget=django_filters.widgets.CSVWidget(),
                                     method='filter_division')

    class Meta:
        model = Place
        fields = ('division',)

    def filter_division(self, queryset, name, value):
        return filter_division(queryset, name, value)


class PlaceRetrieveViewSet(GeoModelAPIView,
                           viewsets.GenericViewSet,
                           mixins.RetrieveModelMixin):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer

    def get_serializer_context(self):
        context = super(PlaceRetrieveViewSet, self).get_serializer_context()
        context.setdefault('skip_fields', set()).add('origin_id')
        return context


class PlaceListViewSet(GeoModelAPIView,
                       viewsets.GenericViewSet,
                       mixins.ListModelMixin):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer
    filter_backends = (filters.DjangoFilterBackend, filters.OrderingFilter)
    filter_class = PlaceFilter
    ordering_fields = ('n_events', 'id', 'name', 'street_address', 'postal_code')
    ordering = ('-n_events',)

    def get_queryset(self):
        """
        Return Place queryset. If request has parameter show_all_places=1
        all Places are returned, otherwise only which have events.
        Additional query parameters:
        event.data_source
        event.start
        event.end
        """
        queryset = Place.objects.prefetch_related('divisions__type', 'divisions__municipality')
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

    def get_serializer_context(self):
        context = super(PlaceListViewSet, self).get_serializer_context()
        context.setdefault('skip_fields', set()).add('origin_id')
        return context

register_view(PlaceRetrieveViewSet, 'place')
register_view(PlaceListViewSet, 'place')


class OpeningHoursSpecificationSerializer(LinkedEventsSerializer):
    class Meta:
        model = OpeningHoursSpecification


class LanguageSerializer(LinkedEventsSerializer):
    view_name = 'language-detail'
    translation_available = serializers.SerializerMethodField()

    class Meta:
        model = Language
        fields = '__all__'

    def get_translation_available(self, obj):
        return obj.id in [language[0] for language in settings.LANGUAGES]


class LanguageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer

register_view(LanguageViewSet, 'language')

LOCAL_TZ = pytz.timezone(settings.TIME_ZONE)


class OrganizationSerializer(LinkedEventsSerializer):
    view_name = 'organization-detail'

    class Meta:
        model = Organization
        exclude = ['admin_users']


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

register_view(OrganizationViewSet, 'organization')


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


class ImageSerializer(LinkedEventsSerializer):
    view_name = 'image-detail'
    license = serializers.PrimaryKeyRelatedField(queryset=License.objects.all(), required=False)

    class Meta:
        model = Image
        fields = '__all__'

    def to_representation(self, obj):
        # the url field is customized based on image and url
        representation = super().to_representation(obj)
        if representation['image']:
            representation['url'] = representation['image']
        representation.pop('image')
        return representation

    def validate(self, data):
        # name the image after the file, if name was not provided
        if 'name' not in data:
            if 'url' in data:
             data['name'] = str(data['url']).rsplit('/', 1)[-1]
            if 'image' in data:
             data['name'] = str(data['image']).rsplit('/', 1)[-1]
        super().validate(data)
        return data


class ImageViewSet(viewsets.ModelViewSet):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    pagination_class = LargeResultsSetPagination
    ordering_fields = ('last_modified_time',)
    ordering = ('-last_modified_time',)

    def get_queryset(self):
        queryset = Image.objects.all()
        publisher = self.request.query_params.get('publisher', None)
        if publisher:
            publisher = publisher.lower().split(',')
            queryset = queryset.filter(publisher__in=publisher)
        data_source = self.request.query_params.get('data_source')
        # Filter by data source, multiple sources separated by comma
        if data_source:
            data_source = data_source.lower().split(',')
            queryset = queryset.filter(data_source__in=data_source)
        return queryset

    def perform_destroy(self, instance):
        # ensure image can only be deleted within the organization
        data_source, organization = get_authenticated_data_source_and_publisher(self.request)
        if not organization == instance.publisher:
                raise PermissionDenied()
        super().perform_destroy(instance)


register_view(ImageViewSet, 'image', base_name='image')


class EventSerializer(LinkedEventsSerializer, GeoModelAPIView):
    id = serializers.CharField(required=False)
    location = JSONLDRelatedField(serializer=PlaceSerializer, required=False,
                                  view_name='place-detail', queryset=Place.objects.all())
    # provider = OrganizationSerializer(hide_ld_context=True)
    keywords = JSONLDRelatedField(serializer=KeywordSerializer, many=True, allow_empty=False,
                                  required=False,
                                  view_name='keyword-detail', queryset=Keyword.objects.filter(deprecated=False))
    super_event = JSONLDRelatedField(serializer='EventSerializer', required=False, view_name='event-detail',
                                     queryset=Event.objects.all(), allow_null=True)
    event_status = EnumChoiceField(Event.STATUSES, required=False)
    publication_status = EnumChoiceField(PUBLICATION_STATUSES)
    external_links = EventLinkSerializer(many=True, required=False)
    offers = OfferSerializer(many=True, required=False)
    data_source = serializers.PrimaryKeyRelatedField(queryset=DataSource.objects.all(),
                                                     required=False)
    publisher = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all(),
                                                   required=False)
    sub_events = JSONLDRelatedField(serializer='EventSerializer',
                                    required=False, view_name='event-detail',
                                    many=True, queryset=Event.objects.all())
    image = JSONLDRelatedField(serializer=ImageSerializer, required=False, allow_null=True,
                               view_name='image-detail', queryset=Image.objects.all(), expanded=True)
    in_language = JSONLDRelatedField(serializer=LanguageSerializer, required=False,
                                     view_name='language-detail', many=True, queryset=Language.objects.all())
    audience = JSONLDRelatedField(serializer=KeywordSerializer, view_name='keyword-detail',
                                  many=True, required=False, queryset=Keyword.objects.filter(deprecated=False))

    view_name = 'event-detail'
    fields_needed_to_publish = ('keywords', 'location', 'start_time', 'short_description', 'description')

    def __init__(self, *args, skip_empties=False, **kwargs):
        super(EventSerializer, self).__init__(*args, **kwargs)
        # The following can be used when serializing when
        # testing and debugging.
        self.skip_empties = skip_empties

    def get_datetimes(self, data):
        for field in ['date_published', 'start_time', 'end_time']:
            val = data.get(field, None)
            if val:
                if isinstance(val, str):
                    data[field] = parse_time(val, True)
        return data

    def to_internal_value(self, data):
        # parse the first image to the image field
        if 'images' in data:
            if data['images']:
                data['image'] = data['images'][0]

        # If the obligatory fields are null or empty, remove them to prevent to_internal_value from checking them.
        # Only for drafts, because null start time of a PUBLIC event will indicate POSTPONED.

        if data.get('publication_status') == 'draft':
            # however, the optional fields cannot be null and must be removed
            for field in self.fields_needed_to_publish:
                if not data.get(field):
                    data.pop(field, None)

        data = super().to_internal_value(data)
        return data

    def validate_id(self, value):
        if value:
            id_data_source_prefix = value.split(':', 1)[0]
            if not id_data_source_prefix == self.data_source.id:
                # the event might be from another data source by the same organization, and we are only editing it
                if self.instance:
                    if self.publisher.owned_systems.filter(id=id_data_source_prefix).exists():
                        return value
                raise serializers.ValidationError(
                    {'id': _("Setting id to %(given)s " +
                             " is not allowed for your organization. The id"
                             " must be left blank or set to %(data_source)s:desired_id") %
                           {'given': str(value), 'data_source': self.data_source}})
        return value

    def validate_publication_status(self, value):
        if not value:
            raise serializers.ValidationError({'publication_status':
                _("You must specify whether you wish to submit a draft or a public event.")})
        return value

    def validate(self, data):
        # clean the html
        for k, v in data.items():
            if k in ["description"]:
                if isinstance(v, str) and any(c in v for c in '<>&'):
                    data[k] = bleach.clean(v, settings.BLEACH_ALLOWED_TAGS)
        data = super().validate(data)

        # if the event is a draft, no further validation is performed
        if data['publication_status'] == PublicationStatus.DRAFT:
            return data

        # check that published events have a location, keyword and start_time
        languages = [x[0] for x in settings.LANGUAGES]

        errors = {}
        lang_error_msg = _('This field must be specified before an event is published.')
        for field in self.fields_needed_to_publish:
            if field in self.translated_fields:
                for lang in languages:
                    name = "name_%s" % lang
                    field_lang = "%s_%s" % (field, lang)
                    if data.get(name) and not data.get(field_lang):
                        errors.setdefault(field, {})[lang] = lang_error_msg
                    if field == 'short_description' and len(data.get(field_lang, [])) > 160:
                        errors.setdefault(field, {})[lang] = (
                            _('Short description length must be 160 characters or less'))

            elif not data.get(field):
                # The start time may be null if a published event is postponed!
                if field == 'start_time' and 'start_time' in data:
                    pass
                else:
                    errors[field] = lang_error_msg

        # published events need price info = at least one offer that is free or not
        offer_exists = False
        for offer in data.get('offers', []):
            if 'is_free' in offer:
                offer_exists = True
                break
        if not offer_exists:
            errors['offers'] = _('Price info must be specified before an event is published.')

        # adjust start_time and has_start_time

        if 'has_start_time' not in data:
            # provided time is assumed exact
            data['has_start_time'] = True
        if not data['has_start_time']:
            # if no exact time is supplied, the event starts at midnight local time
            data['start_time'] = timezone.localtime(data['start_time']).\
                replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)

        # adjust end_time and has_end_time

        # If no end timestamp supplied, we treat the event as ending at midnight.
        if 'end_time' not in data or not data['end_time']:
            data['end_time'] = data['start_time']
            data['has_end_time'] = False
        if 'has_end_time' not in data:
            # provided time is assumed exact
            data['has_end_time'] = True
        if not data['has_end_time']:
            # if no exact time is supplied, the event ends at midnight local time
            data['end_time'] = timezone.localtime(data['end_time'])\
                .replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
            data['end_time'] += timedelta(days=1)

        if data.get('start_time') and data['start_time'] < timezone.now():
            errors['start_time'] = force_text(_('Start time cannot be in the past.'))

        if data.get('end_time') and data['end_time'] < timezone.now():
            errors['end_time'] = force_text(_('End time cannot be in the past.'))

        if errors:
            raise serializers.ValidationError(errors)

        return data

    def create(self, validated_data):
        # if id was not provided, we generate it upon creation:
        if 'id' not in validated_data:
            validated_data['id'] = generate_id(self.data_source)

        offers = validated_data.pop('offers', [])
        links = validated_data.pop('external_links', [])

        validated_data.update({'created_by': self.user,
                               'last_modified_by': self.user,
                               'created_time': Event.now(),  # we must specify creation time as we are setting id
                               'event_status': Event.Status.SCHEDULED,  # mark all newly created events as scheduled
                               })
        event = super().create(validated_data)

        # create and add related objects
        for offer in offers:
            Offer.objects.create(event=event, **offer)
        for link in links:
            EventLink.objects.create(event=event, **link)

        return event

    def update(self, instance, validated_data):
        offers = validated_data.pop('offers', None)
        links = validated_data.pop('external_links', None)

        if instance.end_time and instance.end_time < timezone.now():
            raise DRFPermissionDenied(_('Cannot edit a past event.'))

        # The API only allows scheduling and cancelling events.
        # POSTPONED and RESCHEDULED may not be set, but should be allowed in already set instances.
        if validated_data.get('event_status') in (Event.Status.POSTPONED, Event.Status.RESCHEDULED):
            if validated_data.get('event_status') != instance.event_status:
                raise serializers.ValidationError({'event_status':
                                                  _('POSTPONED and RESCHEDULED statuses cannot be set directly.'
                                                    'Changing event start_time or marking start_time null'
                                                    'will reschedule or postpone an event.')})

        # Update event_status if a PUBLIC SCHEDULED or CANCELLED event start_time is updated.
        # DRAFT events will remain SCHEDULED up to publication.
        # Check that the event is not explicitly CANCELLED at the same time.
        if (instance.publication_status == PublicationStatus.PUBLIC and
                    validated_data.get('event_status', Event.Status.SCHEDULED) != Event.Status.CANCELLED):
            # if the instance was ever CANCELLED, RESCHEDULED or POSTPONED, it may never be SCHEDULED again
            if instance.event_status != Event.Status.SCHEDULED:
                if validated_data.get('event_status') == Event.Status.SCHEDULED:
                    raise serializers.ValidationError({'event_status':
                                                       _('Public events cannot be set back to SCHEDULED if they'
                                                         'have already been CANCELLED, POSTPONED or RESCHEDULED.')})
                validated_data['event_status'] = instance.event_status
            try:
                # if the start_time changes, reschedule the event
                if validated_data['start_time'] != instance.start_time:
                    validated_data['event_status'] = Event.Status.RESCHEDULED
                # if the posted start_time is null, postpone the event
                if not validated_data['start_time']:
                    validated_data['event_status'] = Event.Status.POSTPONED
            except KeyError:
                # if the start_time is not provided, do nothing
                pass

        # update validated fields
        super().update(instance, validated_data)

        # update offers
        if isinstance(offers, list):
            instance.offers.all().delete()
            for offer in offers:
                Offer.objects.create(event=instance, **offer)

        # update ext links
        if isinstance(links, list):
            instance.external_links.all().delete()
            for link in links:
                EventLink.objects.create(event=instance, **link)

        return instance

    def to_representation(self, obj):
        ret = super(EventSerializer, self).to_representation(obj)
        if 'start_time' in ret and not obj.has_start_time:
            # Return only the date part
            ret['start_time'] = obj.start_time.astimezone(LOCAL_TZ).strftime('%Y-%m-%d')
        if 'end_time' in ret and not obj.has_end_time:
            # If we're storing only the date part, do not pretend we have the exact time.
            # Timestamp is of the form %Y-%m-%dT00:00:00, so we report the previous date.
            ret['end_time'] = (obj.end_time - timedelta(days=1)).astimezone(LOCAL_TZ).strftime('%Y-%m-%d')
            # Unless the event is short, then no need for end time
            if obj.end_time - obj.start_time <= timedelta(days=1):
                ret['end_time'] = None
        del ret['has_start_time']
        del ret['has_end_time']
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
        if 'image' in ret:
            if ret['image'] == None:
                ret['images'] = []
            else:
                ret['images'] = [ret['image']]
            del ret['image']
        request = self.context.get('request')
        if request:
            if not request.user.is_authenticated():
                del ret['publication_status']
        return ret

    class Meta:
        model = Event
        exclude = ['deleted']
        list_serializer_class = BulkListSerializer


def _format_images_v0_1(data):
    if 'images' not in data:
        return
    images = data.get('images')
    del data['images']
    if len(images) == 0:
        data['image'] = None
    else:
        data['image'] = images[0].get('url', None)

class EventSerializerV0_1(EventSerializer):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('context', {}).setdefault('include', []).append('image')
        super(EventSerializerV0_1, self).__init__(*args, **kwargs)

    def to_representation(self, obj):
        ret = super(EventSerializerV0_1, self).to_representation(obj)
        _format_images_v0_1(ret)
        return ret

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
        except (TypeError, ValueError):
            raise ParseError('time in invalid format (try ISO 8601 or yyyy-mm-dd)')
    return dt



class LinkedEventsOrderingFilter(filters.OrderingFilter):
    ordering_param = 'sort'


class EventOrderingFilter(LinkedEventsOrderingFilter):
    def filter_queryset(self, request, queryset, view):
        queryset = super(EventOrderingFilter, self).filter_queryset(request, queryset, view)
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            ordering = []
        if 'days_left' in [x.lstrip('-') for x in ordering]:
            queryset = queryset.extra(select={'days_left': 'date_part(\'day\', end_time - start_time)'})
        return queryset


def parse_duration_string(duration):
    """
    Parse duration string expressed in format
    86400 or 86400s (24 hours)
    180m or 3h (3 hours)
    3d (3 days)
    """
    m = re.match(r'(\d+)\s*(d|h|m|s)?$', duration.strip().lower())
    if not m:
        raise ParseError("Invalid duration supplied. Try '1d', '2h' or '180m'.")
    val, unit = m.groups()
    if not unit:
        unit = 's'

    if unit == 's':
        mul = 1
    elif unit == 'm':
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

    # Filter by data source, multiple sources separated by comma
    val = params.get('data_source', None)
    if val:
        val = val.split(',')
        queryset = queryset.filter(data_source_id__in=val)

    # Negative filter by data source, multiple sources separated by comma
    val = params.get('data_source!', None)
    if val:
        val = val.split(',')
        queryset = queryset.exclude(data_source_id__in=val)

    # Filter by location id, multiple ids separated by comma
    val = params.get('location', None)
    if val:
        val = val.split(',')
        queryset = queryset.filter(location_id__in=val)

    # Filter by keyword id, multiple ids separated by comma
    val = params.get('keyword', None)
    if val:
        val = val.split(',')
        queryset = queryset.filter(Q(keywords__pk__in=val) | Q(audience__pk__in=val)).distinct()

    # Filter only super or sub events if recurring has value
    val = params.get('recurring', None)
    if val:
        val = val.lower()
        if val == 'super':
            queryset = queryset.filter(super_event_type=Event.SuperEventType.RECURRING)
        elif val == 'sub':
            queryset = queryset.exclude(super_event_type=Event.SuperEventType.RECURRING)

    val = params.get('max_duration', None)
    if val:
        dur = parse_duration_string(val)
        cond = 'end_time - start_time <= %s :: interval'
        queryset = queryset.extra(where=[cond], params=[str(dur)])

    val = params.get('min_duration', None)
    if val:
        dur = parse_duration_string(val)
        cond = 'end_time - start_time >= %s :: interval'
        queryset = queryset.extra(where=[cond], params=[str(dur)])

    # Filter by publisher, multiple sources separated by comma
    val = params.get('publisher', None)
    if val:
        val = val.split(',')
        queryset = queryset.filter(publisher__id__in=val)

    return queryset


class EventFilter(filters.FilterSet):
    division = django_filters.Filter(name='location__divisions', lookup_expr='in',
                              widget=django_filters.widgets.CSVWidget(),
                              method='filter_division')
    super_event_type = django_filters.CharFilter(method='filter_super_event_type')

    class Meta:
        model = Event
        fields = ('division', 'super_event_type')

    def filter_super_event_type(self, queryset, name, value):
        if value in ('null', 'none'):
            value = None
        return queryset.filter(super_event_type=value)

    def filter_division(self, queryset, name, value):
        return filter_division(queryset, name, value)


class EventViewSet(BulkModelViewSet, JSONAPIViewSet):
    queryset = Event.objects.filter(deleted=False)
    # This exclude is, atm, a bit overkill, considering it causes a massive query and no such events exist.
    # queryset = queryset.exclude(super_event_type=Event.SuperEventType.RECURRING, sub_events=None)
    # Use select_ and prefetch_related() to reduce the amount of queries
    queryset = queryset.select_related('location')
    queryset = queryset.prefetch_related(
        'offers', 'keywords', 'audience', 'external_links', 'sub_events', 'in_language')
    serializer_class = EventSerializer
    filter_backends = (EventOrderingFilter, filters.DjangoFilterBackend)
    filter_class = EventFilter
    ordering_fields = ('start_time', 'end_time', 'days_left', 'last_modified_time')
    ordering = ('-last_modified_time',)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_source = None
        self.organization = None

    @staticmethod
    def get_serializer_class_for_version(version):
        if version == 'v0.1':
            return EventSerializerV0_1
        return EventSerializer

    def get_serializer_class(self):
        return EventViewSet.get_serializer_class_for_version(self.request.version)

    def get_serializer_context(self):
        context = super(EventViewSet, self).get_serializer_context()
        context.setdefault('skip_fields', set()).update(set([
            'headline',
            'secondary_headline']))
        return context

    def get_object(self):
        self.data_source, self.organization = get_authenticated_data_source_and_publisher(self.request)
        # Overridden to prevent queryset filtering from being applied
        # outside list views.
        try:
            event = Event.objects.get(pk=self.kwargs['pk'])
        except Event.DoesNotExist:
            raise Http404("Event does not exist")
        if (event.publication_status == PublicationStatus.PUBLIC or
            self.organization == event.publisher):
            return event
        else:
            raise Http404("Event does not exist")

    def filter_queryset(self, queryset):
        """
        TODO: convert to use proper filter framework
        """
        self.data_source, self.organization = get_authenticated_data_source_and_publisher(self.request)
        queryset = super(EventViewSet, self).filter_queryset(queryset)
        auth_filters = Q(publication_status=PublicationStatus.PUBLIC)
        if self.organization:
            # USER IS AUTHENTICATED
            if 'show_all' in self.request.query_params:
                # Show all events for this organization,
                # along with public events for others.
                auth_filters |= Q(publisher=self.organization)
        queryset = queryset.filter(auth_filters)
        queryset = _filter_event_queryset(queryset, self.request.query_params,
                                          srs=self.srs)
        return queryset.filter()

    def allow_bulk_destroy(self, qs, filtered):
        return False

    @atomic
    def bulk_update(self, request, *args, **kwargs):
        self.data_source, self.organization = get_authenticated_data_source_and_publisher(self.request)
        return super().bulk_update(request, *args, **kwargs)

    @atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


register_view(EventViewSet, 'event')


class SearchSerializer(serializers.Serializer):
    def to_representation(self, search_result):
        model = search_result.model
        version = self.context['request'].version
        ser_class = get_serializer_for_model(model, version=version)
        assert ser_class is not None, "Serializer for %s not found" % model
        data = ser_class(search_result.object, context=self.context).data
        data['resource_type'] = model._meta.model_name
        data['score'] = search_result.score
        return data


class SearchSerializerV0_1(SearchSerializer):
    def to_representation(self, search_result):
        ret = super(SearchSerializerV0_1, self).to_representation(search_result)
        if 'resource_type' in ret:
            ret['object_type'] = ret['resource_type']
            del ret['resource_type']
        return ret

DATE_DECAY_SCALE = '30d'


class SearchViewSet(GeoModelAPIView, viewsets.ViewSetMixin, generics.ListAPIView):
    def get_serializer_class(self):
        if self.request.version == 'v0.1':
            return SearchSerializerV0_1
        return SearchSerializer

    def list(self, request, *args, **kwargs):
        languages = [x[0] for x in settings.LANGUAGES]

        # If the incoming language is not specified, go with the default.
        self.lang_code = request.query_params.get('language', languages[0])
        if self.lang_code not in languages:
            raise ParseError("Invalid language supplied. Supported languages: %s" %
                             ','.join(languages))

        params = request.query_params

        input_val = params.get('input', '').strip()
        q_val = params.get('q', '').strip()
        if not input_val and not q_val:
            raise ParseError("Supply search terms with 'q=' or autocomplete entry with 'input='")
        if input_val and q_val:
            raise ParseError("Supply either 'q' or 'input', not both")

        old_language = translation.get_language()[:2]
        translation.activate(self.lang_code)

        queryset = SearchQuerySet()
        if input_val:
            queryset = queryset.filter(autosuggest=input_val)
        else:
            queryset = queryset.filter(text=AutoQuery(q_val))

        models = None
        types = params.get('type', '').split(',')
        if types:
            models = set()
            for t in types:
                if t == 'event':
                    models.add(Event)
                elif t == 'place':
                    models.add(Place)

        if self.request.version == 'v0.1':
            if len(models) == 0:
                models.add(Event)

        if len(models) == 1 and Event in models:
            start = params.get('start', None)
            if start:
                dt = parse_time(start, is_start=True)
                queryset = queryset.filter(Q(end_time__gt=dt) | Q(start_time__gte=dt))

            end = params.get('end', None)
            if end:
                dt = parse_time(end, is_start=False)
                queryset = queryset.filter(Q(end_time__lt=dt) | Q(start_time__lte=dt))

            if not start and not end and hasattr(queryset.query, 'add_decay_function'):
                # If no time-based filters are set, make the relevancy score
                # decay the further in the future the event is.
                now = datetime.utcnow()
                queryset = queryset.filter(end_time__gt=now).decay({
                    'gauss': {
                        'end_time': {
                            'origin': now,
                            'scale': DATE_DECAY_SCALE
                        }
                    }
                })

        if len(models) > 0:
            queryset = queryset.models(*list(models))

        self.object_list = queryset.load_all()

        page = self.paginate_queryset(self.object_list)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            resp = self.get_paginated_response(serializer.data)
            translation.activate(old_language)
            return resp

        serializer = self.get_serializer(self.object_list, many=True)
        resp = Response(serializer.data)

        translation.activate(old_language)

        return resp


register_view(SearchViewSet, 'search', base_name='search')
