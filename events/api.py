# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# python
import base64
import re
import struct
import time
import urllib.parse
from copy import deepcopy
from datetime import datetime, timedelta
from functools import partial

# django and drf
from django.db.transaction import atomic
from django.http import Http404, HttpResponsePermanentRedirect
from django.utils import translation
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db.utils import IntegrityError
from django.conf import settings
from django.urls import NoReverseMatch
from django.db.models import Q, QuerySet
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.utils.encoding import force_text
from rest_framework import (
    serializers, relations, viewsets, mixins, filters, generics, permissions
)
from rest_framework.filters import BaseFilterBackend
from rest_framework.permissions import SAFE_METHODS
from rest_framework.settings import api_settings
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework.exceptions import ParseError, PermissionDenied as DRFPermissionDenied, APIException
from rest_framework.views import get_view_name as original_get_view_name
from rest_framework.routers import APIRootView
from rest_framework.fields import DateTimeField


# 3rd party
from isodate import Duration, duration_isoformat, parse_duration
from modeltranslation.translator import translator, NotRegistered
from haystack.query import AutoQuery
from munigeo.api import (
    GeoModelSerializer, GeoModelAPIView, build_bbox_filter, srid_to_srs
)
from munigeo.models import AdministrativeDivision
from rest_framework_bulk import BulkListSerializer, BulkModelViewSet, BulkSerializerMixin
import pytz
import bleach
import django_filters

from django_orghierarchy.models import Organization

# events
from events import utils
from events.api_pagination import LargeResultsSetPagination
from events.auth import ApiKeyAuth, ApiKeyUser
from events.custom_elasticsearch_search_backend import (
    CustomEsSearchQuerySet as SearchQuerySet
)
from events.extensions import apply_select_and_prefetch, get_extensions_from_request
from events.models import (
    Place, Event, Keyword, KeywordSet, Language, OpeningHoursSpecification, EventLink,
    Offer, DataSource, Image, PublicationStatus, PUBLICATION_STATUSES, License, Video
)
from events.translation import EventTranslationOptions
from helevents.models import User
from events.renderers import DOCXRenderer
from events.signals import post_save, post_update

def get_view_name(view):
    if type(view) is APIRootView:
        return getattr(settings, 'INSTANCE_NAME', 'Linked Events')
    return original_get_view_name(view)


viewset_classes_by_model = {}

all_views = []


def register_view(klass, name, basename=None):
    entry = {'class': klass, 'name': name}
    if basename is not None:
        entry['basename'] = basename
    all_views.append(entry)
    if klass.serializer_class and \
            hasattr(klass.serializer_class, 'Meta') and \
            hasattr(klass.serializer_class.Meta, 'model'):
        model = klass.serializer_class.Meta.model
        viewset_classes_by_model[model] = klass


def get_serializer_for_model(model, version='v1'):
    Viewset = viewset_classes_by_model.get(model)
    if Viewset is None:
        return None
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
        # objects *created* by api are marked coming from the system data source unless api_key is provided
        # we must optionally create the system data source here, as the settings may have changed at any time
        system_data_source_defaults = {'user_editable': True}
        data_source, created = DataSource.objects.get_or_create(id=settings.SYSTEM_DATA_SOURCE_ID,
                                                                defaults=system_data_source_defaults)
        # user organization is used unless api_key is provided
        user = request.user
        if isinstance(user, User):
            publisher = user.get_default_organization()
        else:
            publisher = None
        # no sense in doing the replacement check later, the authenticated publisher must be current to begin with
        if publisher and publisher.replaced_by:
            publisher = publisher.replaced_by
    return data_source, publisher


def get_publisher_query(publisher):
    """Get query for publisher (Organization)

    Some organizations can be replaced by a new organization.
    We need to return objects that reference on replaced
    organization when querying the new organization, and vice
    versa.

    :param publisher: a or a list of filtering organizations
    :type publisher: str, Organization, list
    :return: the query that check both replaced and new organization
    """
    if isinstance(publisher, list):
        q = Q(
            publisher__in=publisher,
        ) | Q(
            publisher__replaced_by__in=publisher,
        ) | Q(
            publisher__replaced_organization__in=publisher,
        )
    else:
        q = Q(
            publisher=publisher,
        ) | Q(
            publisher__replaced_by=publisher,
        ) | Q(
            publisher__replaced_organization=publisher,
        )

    return q


def clean_text_fields(data, allowed_html_fields=[]):
    for k, v in data.items():
        if isinstance(v, str) and any(c in v for c in '<>&'):
            # only specified fields may contain allowed tags
            for field_name in allowed_html_fields:
                # check all languages and the default translation field too
                if k.startswith(field_name):
                    data[k] = bleach.clean(v, settings.BLEACH_ALLOWED_TAGS)
                    break
            else:
                data[k] = bleach.clean(v)
                # for non-html data, ampersands should be bare
                data[k] = data[k].replace('&amp;', '&')
    return data


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
            context = self.context.copy()
            # To avoid infinite recursion, only include sub/super events one level at a time
            if 'include' in context:
                context['include'] = [x for x in context['include'] if x != 'sub_events' and x != 'super_event']
            return self.related_serializer(obj, hide_ld_context=self.hide_ld_context,
                                           context=context).data
        link = super(JSONLDRelatedField, self).to_representation(obj)
        if link is None:
            return None
        return {
            '@id': link
        }

    def to_internal_value(self, value):
        # TODO: JA If @id is missing, this will complain just about value not being JSON
        if not isinstance(value, dict) or '@id' not in value:
            raise serializers.ValidationError(self.invalid_json_error % type(value).__name__)

        url = value['@id']
        if not url:
            if self.required:
                raise serializers.ValidationError(_('This field is required.'))
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
                value.days * 24 * 3600 * 1000000 +
                value.seconds * 1000 +
                value.microseconds / 1000
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
        lang_codes = utils.get_fixed_lang_codes()
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
                raise serializers.ValidationError({field_name: 'This field is a translated field. Instead of a string,'
                                                   ' you must supply an object with strings corresponding'
                                                   ' to desired language ids.'})
            for language in (lang for lang in utils.get_fixed_lang_codes() if lang in obj):
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
            for lang in utils.get_fixed_lang_codes():
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
    system_generated_fields = ('created_time', 'last_modified_time', 'created_by', 'last_modified_by')
    only_admin_visible_fields = ('created_by', 'last_modified_by')

    def __init__(self, instance=None, files=None,
                 context=None, partial=False, many=None, skip_fields=set(),
                 allow_add_remove=False, hide_ld_context=False, **kwargs):
        super(LinkedEventsSerializer, self).__init__(
            instance=instance, context=context, **kwargs)
        if context is None:
            return
        if 'request' in context:
            self.request = context['request']

        # for post and put methods as well as field visibility, user information is needed
        self.method = self.request.method
        if 'user' in context:
            self.user = context['user']
        if 'admin_tree_ids' in context:
            self.admin_tree_ids = context['admin_tree_ids']

        # by default, admin fields are skipped
        self.skip_fields = skip_fields | set(self.only_admin_visible_fields)

        if context is not None:
            # query allows non-skipped fields to be expanded
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
            # query allows additional fields to be skipped
            self.skip_fields |= context.get('skip_fields', set())

        self.hide_ld_context = hide_ld_context

        if self.method in permissions.SAFE_METHODS:
            return
        # post and put methods need further authentication
        self.data_source, self.publisher = get_authenticated_data_source_and_publisher(self.request)
        if not self.publisher:
            raise PermissionDenied(_("User doesn't belong to any organization"))
        # in case of bulk operations, the instance may be a huge queryset, already filtered by permission
        # therefore, we only do permission checks for single instances
        if not isinstance(instance, QuerySet) and instance:
            # check permissions *before* validation
            if isinstance(self.user, ApiKeyUser):
                # allow updating only if the api key matches instance data source
                if not instance.data_source == self.data_source:
                    raise PermissionDenied()
            else:
                # without api key, the user will have to be admin
                if not instance.is_user_editable() or not instance.can_be_edited_by(self.user):
                    # An exception to allow users to publish events using default images from the Imagebank
                    # even if they aren't bound to the Imagebank-organization for regular or admin rights.
                    if not isinstance(instance, Image):
                        raise PermissionDenied()

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
        # display non-public fields if 1) obj has publisher org and 2) user belongs to the same org tree
        # never modify self.skip_fields, as it survives multiple calls in the serializer across objects
        obj_skip_fields = set(self.skip_fields)
        if self.user and hasattr(obj, 'publisher') and obj.publisher and obj.publisher.tree_id in self.admin_tree_ids:
            for field in self.only_admin_visible_fields:
                obj_skip_fields.remove(field)
        for field in obj_skip_fields:
            if field in ret:
                del ret[field]
        return ret

    def validate_data_source(self, value):
        # a single POST always comes from a single source
        if value and self.method == 'POST':
            if value != self.data_source:
                raise DRFPermissionDenied(
                    {'data_source': _(
                        "Setting data_source to %(given)s " +
                        " is not allowed for this user. The data_source"
                        " must be left blank or set to %(required)s ") %
                        {'given': str(value), 'required': self.data_source}})
        return value

    def validate_id(self, value):
        # a single POST always comes from a single source
        if value and self.method == 'POST':
            id_data_source_prefix = value.split(':', 1)[0]
            if not id_data_source_prefix == self.data_source.id:
                # if we are creating, there's no excuse to have any other data source than the request gave
                raise serializers.ValidationError(
                    {'id': _(
                        "Setting id to %(given)s " +
                        " is not allowed for your organization. The id"
                        " must be left blank or set to %(data_source)s:desired_id") %
                        {'given': str(value), 'data_source': self.data_source}})
        return value

    def validate_publisher(self, value):
        # a single POST always comes from a single source
        if value and self.method == 'POST':
            if value not in (set(self.user.get_admin_organizations_and_descendants())
                             | set(map(lambda x: getattr(x, 'replaced_by'),
                                   self.user.get_admin_organizations_and_descendants()))
                             | set(self.user.organization_memberships.all())
                             | set(map(lambda x: getattr(x, 'replaced_by'),
                                   self.user.organization_memberships.all()))):
                raise serializers.ValidationError(
                    {'publisher': _(
                        "Setting publisher to %(given)s " +
                        " is not allowed for this user. The publisher" +
                        " must be left blank or set to %(required)s or any other organization"
                        " the user belongs to.") %
                        {'given': str(value),
                         'required': str(self.publisher
                                         if not self.publisher.replaced_by
                                         else self.publisher.replaced_by)}})
            if value.replaced_by:
                # for replaced organizations, we automatically update to the current organization
                # even if the POST uses the old id
                return value.replaced_by
        return value

    def validate(self, data):
        if 'name' in self.translated_fields:
            name_exists = False
            languages = [x[0] for x in settings.LANGUAGES]
            for language in languages:
                # null or empty strings are not allowed, they are the same as missing name!
                if 'name_%s' % language in data and data['name_%s' % language]:
                    name_exists = True
                    break
        else:
            # null or empty strings are not allowed, they are the same as missing name!
            name_exists = 'name' in data and data['name']
        if not name_exists:
            raise serializers.ValidationError({'name': _('The name must be specified.')})
        super().validate(data)
        return data

    def create(self, validated_data):
        if 'data_source' not in validated_data:
            validated_data['data_source'] = self.data_source
        # data source has already been validated
        if 'publisher' not in validated_data:
            validated_data['publisher'] = self.publisher
        # publisher has already been validated
        validated_data['created_by'] = self.user
        validated_data['last_modified_by'] = self.user
        try:
            instance = super().create(validated_data)
        except IntegrityError as error:
            if 'duplicate' and 'pkey' in str(error):
                raise serializers.ValidationError({'id': _("An object with given id already exists.")})
            else:
                raise error
        return instance

    def update(self, instance, validated_data):
        validated_data['last_modified_by'] = self.user

        if 'id' in validated_data:
            if instance.id != validated_data['id']:
                raise serializers.ValidationError({'id': _("You may not change the id of an existing object.")})
        if 'publisher' in validated_data:
            if validated_data['publisher'] not in (instance.publisher, instance.publisher.replaced_by):
                raise serializers.ValidationError(
                    {'publisher': _("You may not change the publisher of an existing object.")}
                    )
        if 'data_source' in validated_data:
            if instance.data_source != validated_data['data_source']:
                raise serializers.ValidationError(
                    {'data_source': _("You may not change the data source of an existing object.")}
                    )
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


def _text_qset_by_translated_field(field, val):
    # Free text search from all languages of the field
    languages = utils.get_fixed_lang_codes()
    qset = Q()
    for lang in languages:
        kwarg = {field + '_' + lang + '__icontains': val}
        qset |= Q(**kwarg)
    return qset


class JSONAPIViewMixin(object):
    def initial(self, request, *args, **kwargs):
        ret = super().initial(request, *args, **kwargs)
        # if srid is not specified, this will yield munigeo default 4326
        self.srs = srid_to_srs(self.request.query_params.get('srid', None))
        # check for NUL strings that crash psycopg2
        for key, param in self.request.query_params.items():
            if u'\x00' in param:
                raise ParseError("A string literal cannot contain NUL (0x00) characters. "
                                 "Please fix query parameter " + param)
        return ret

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # user admin ids must be injected to the context for nested serializers, to avoid duplicating work
        user = context['request'].user
        admin_tree_ids = set()
        if user and user.is_authenticated:
            admin_tree_ids = user.get_admin_tree_ids()
        context['user'] = user
        context['admin_tree_ids'] = admin_tree_ids
        include = self.request.query_params.get('include', '')
        context['include'] = [x.strip() for x in include.split(',') if x]
        context['srs'] = self.srs
        context.setdefault('skip_fields', set()).add('origin_id')
        return context


class KeywordSerializer(LinkedEventsSerializer):
    view_name = 'keyword-detail'
    alt_labels = serializers.SlugRelatedField(slug_field='name', read_only=True, many=True)
    created_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)
    last_modified_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)

    class Meta:
        model = Keyword
        exclude = ('n_events_changed',)


class KeywordRetrieveViewSet(JSONAPIViewMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Keyword.objects.all()
    queryset = queryset.select_related('publisher')
    serializer_class = KeywordSerializer

    def retrieve(self, request, *args, **kwargs):
        try:
            keyword = Keyword.objects.get(pk=kwargs['pk'])
        except Keyword.DoesNotExist:
            raise Http404()
        if keyword.replaced_by:
            keyword = keyword.get_replacement()
            return HttpResponsePermanentRedirect(reverse('keyword-detail',
                                                         kwargs={'pk': keyword.pk},
                                                         request=request))
        return super().retrieve(request, *args, **kwargs)


class KeywordListViewSet(JSONAPIViewMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Keyword.objects.all()
    queryset = queryset.select_related('publisher').prefetch_related('alt_labels__name')
    serializer_class = KeywordSerializer
    filter_backends = (filters.OrderingFilter,)
    ordering_fields = ('n_events', 'id', 'name', 'data_source')
    ordering = ('-data_source', '-n_events', 'name')

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
            # Also consider alternative labels to broaden the search!
            qset = _text_qset_by_translated_field('name', val) | Q(alt_labels__name__icontains=val)
            queryset = queryset.filter(qset).distinct()
        return queryset


register_view(KeywordRetrieveViewSet, 'keyword')
register_view(KeywordListViewSet, 'keyword')


class KeywordSetSerializer(LinkedEventsSerializer):
    view_name = 'keywordset-detail'
    keywords = JSONLDRelatedField(
        serializer=KeywordSerializer, many=True, required=True, allow_empty=False,
        view_name='keyword-detail', queryset=Keyword.objects.all())
    usage = EnumChoiceField(KeywordSet.USAGES)
    created_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)
    last_modified_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)

    class Meta:
        model = KeywordSet
        fields = '__all__'


class KeywordSetViewSet(JSONAPIViewMixin, viewsets.ReadOnlyModelViewSet):
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
    if hasattr(queryset, 'distinct'):
        # do the join with Q objects (not querysets) in case the queryset has extra fields that would crash qs join
        query = Q(**{name + '__ocd_id__in': ocd_ids}) | Q(**{name + '__name__in': names})
        return (queryset.filter(query)).distinct()
    else:
        # Haystack SearchQuerySet does not support distinct, so we only support one type of search at a time:
        if ocd_ids:
            return queryset.filter(**{name + '__ocd_id__in': ocd_ids})
        else:
            return queryset.filter(**{name + '__name__in': names})


class PlaceSerializer(LinkedEventsSerializer, GeoModelSerializer):
    view_name = 'place-detail'
    divisions = DivisionSerializer(many=True, read_only=True)
    created_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)
    last_modified_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)

    class Meta:
        model = Place
        exclude = ('n_events_changed',)


class PlaceFilter(django_filters.rest_framework.FilterSet):
    division = django_filters.Filter(field_name='divisions', lookup_expr='in',
                                     widget=django_filters.widgets.CSVWidget(),
                                     method='filter_division')

    class Meta:
        model = Place
        fields = ('division',)

    def filter_division(self, queryset, name, value):
        return filter_division(queryset, name, value)


class PlaceRetrieveViewSet(JSONAPIViewMixin, GeoModelAPIView,
                           viewsets.GenericViewSet,
                           mixins.RetrieveModelMixin):
    queryset = Place.objects.all()
    queryset = queryset.select_related('publisher')
    serializer_class = PlaceSerializer

    def retrieve(self, request, *args, **kwargs):
        try:
            place = Place.objects.get(pk=kwargs['pk'])
        except Place.DoesNotExist:
            raise Http404()
        if place.deleted:
            if place.replaced_by:
                place = place.get_replacement()
                return HttpResponsePermanentRedirect(reverse('place-detail',
                                                             kwargs={'pk': place.pk},
                                                             request=request))
        return super().retrieve(request, *args, **kwargs)


class PlaceListViewSet(JSONAPIViewMixin, GeoModelAPIView,
                       viewsets.GenericViewSet,
                       mixins.ListModelMixin):
    queryset = Place.objects.all()
    queryset = queryset.select_related('publisher')
    serializer_class = PlaceSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = PlaceFilter
    ordering_fields = ('n_events', 'id', 'name', 'data_source', 'street_address', 'postal_code')
    ordering = ('-n_events', '-data_source', 'name')  # we want to display tprek before osoite etc.

    def get_queryset(self):
        """
        Return Place queryset.

        If the request has no filter parameters, we only return places that meet the following criteria:
        -the place has events
        -the place is not deleted

        Supported places filtering parameters:
        data_source (only places with the given data sources are included)
        filter (only places containing the specified string are included)
        show_all_places (places without events are included)
        show_deleted (deleted places are included)
        """
        queryset = Place.objects.prefetch_related('divisions__type', 'divisions__municipality')
        data_source = self.request.query_params.get('data_source')
        # Filter by data source, multiple sources separated by comma
        if data_source:
            data_source = data_source.lower().split(',')
            queryset = queryset.filter(data_source__in=data_source)
        if not self.request.query_params.get('show_all_places'):
            queryset = queryset.filter(n_events__gt=0)
        if not self.request.query_params.get('show_deleted'):
            queryset = queryset.filter(deleted=False)

        # Optionally filter places by filter parameter,
        # can be used e.g. with typeahead.js
        # match to street as well as name, to make it easier to find units by address
        val = self.request.query_params.get('text') or self.request.query_params.get('filter')
        if val:
            qset = _text_qset_by_translated_field('name', val) | _text_qset_by_translated_field('street_address', val)
            queryset = queryset.filter(qset)
        return queryset


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
        return obj.id in utils.get_fixed_lang_codes()


class LanguageViewSet(JSONAPIViewMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer


register_view(LanguageViewSet, 'language')

LOCAL_TZ = pytz.timezone(settings.TIME_ZONE)


class OrganizationSerializer(LinkedEventsSerializer):
    view_name = 'organization-detail'

    parent_organization = serializers.HyperlinkedRelatedField(
        queryset=Organization.objects.all(),
        source='parent',
        view_name='organization-detail',
    )
    sub_organizations = serializers.HyperlinkedRelatedField(
        queryset=Organization.objects.all(),
        view_name='organization-detail',
        many=True,
    )
    affiliated_organizations = serializers.HyperlinkedRelatedField(
        queryset=Organization.objects.all(),
        view_name='organization-detail',
        many=True,
    )
    replaced_by = serializers.HyperlinkedRelatedField(
        queryset=Organization.objects.all(),
        view_name='organization-detail',
    )
    is_affiliated = serializers.SerializerMethodField()
    has_regular_users = serializers.SerializerMethodField()
    created_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)
    last_modified_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)

    class Meta:
        model = Organization
        fields = (
            'id', 'data_source', 'origin_id',
            'classification', 'name', 'founding_date',
            'dissolution_date', 'parent_organization',
            'sub_organizations', 'affiliated_organizations',
            'created_time', 'last_modified_time', 'created_by',
            'last_modified_by', 'is_affiliated', 'replaced_by',
            'has_regular_users'
        )

    def get_is_affiliated(self, obj):
        return obj.internal_type == Organization.AFFILIATED

    def get_has_regular_users(self, obj):
        return obj.regular_users.count() > 0


class OrganizationViewSet(JSONAPIViewMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        queryset = Organization.objects.all()

        id = self.request.query_params.get('child', None)
        if id:
            queryset = queryset.get(id=id).get_ancestors()

        id = self.request.query_params.get('parent', None)
        if id:
            queryset = queryset.get(id=id).get_descendants()

        return queryset


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
    created_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)
    last_modified_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)
    created_by = serializers.StringRelatedField(required=False, allow_null=True)
    last_modified_by = serializers.StringRelatedField(required=False, allow_null=True)

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
        if 'name' not in data or not data['name']:
            if 'url' in data:
                data['name']['fi'] = str(data['url']).rsplit('/', 1)[-1]
            if 'image' in data:
                data['name']['fi'] = str(data['image']).rsplit('/', 1)[-1]
        super().validate(data)
        return data
    
    def to_internal_value(self, data):
        if 'image' in data and isinstance(data['image'],str) and ';base64,' in data['image']:
            if 'file_name' in data:
                img_name = data['file_name'] + '.'
            else:
                img_name = 'image' + '.'
            
            formatt, imgstr = data['image'].split(';base64,')
            ext = formatt.split('/')[-1]
            data['image'] = ContentFile(base64.b64decode(imgstr), name=img_name + ext)
        data = super().to_internal_value(data)
        return data
    

class ImageViewSet(JSONAPIViewMixin, viewsets.ModelViewSet):
    queryset = Image.objects.all()
    queryset = queryset.select_related('publisher')
    serializer_class = ImageSerializer
    pagination_class = LargeResultsSetPagination
    filter_backends = (filters.OrderingFilter,)
    ordering_fields = ('last_modified_time',)
    ordering = ('-last_modified_time',)

    def get_queryset(self):
        queryset = Image.objects.all()
        publisher = self.request.query_params.get('publisher', None)
        if publisher:
            publisher = publisher.lower().split(',')
            q = get_publisher_query(publisher)
            queryset = queryset.filter(q)

        data_source = self.request.query_params.get('data_source')
        # Filter by data source, multiple sources separated by comma
        if data_source:
            data_source = data_source.lower().split(',')
            queryset = queryset.filter(data_source__in=data_source)

        created_by = self.request.query_params.get('created_by')
        if created_by:
            if self.request.user.is_authenticated:
                # only displays events by the particular user
                queryset = queryset.filter(created_by=self.request.user)
            else:
                queryset = queryset.none()
        return queryset

    def perform_destroy(self, instance):
        # ensure image can only be deleted within the organization
        data_source, organization = get_authenticated_data_source_and_publisher(self.request)
        if not organization == instance.publisher:
            raise PermissionDenied()
        super().perform_destroy(instance)


register_view(ImageViewSet, 'image', basename='image')


class VideoSerializer(TranslatedModelSerializer, serializers.ModelSerializer):
    def to_representation(self, obj):
        ret = super().to_representation(obj)
        if not ret['name']:
            ret['name'] = None
        return ret

    class Meta:
        model = Video
        exclude = ['id', 'event']


class EventSerializer(BulkSerializerMixin, LinkedEventsSerializer, GeoModelAPIView):
    id = serializers.CharField(required=False)
    location = JSONLDRelatedField(serializer=PlaceSerializer, required=False, allow_null=True,
                                  view_name='place-detail', queryset=Place.objects.all())
    # provider = OrganizationSerializer(hide_ld_context=True)
    keywords = JSONLDRelatedField(serializer=KeywordSerializer, many=True, allow_empty=True,
                                  required=False,
                                  view_name='keyword-detail', queryset=Keyword.objects.filter(deprecated=False))
    super_event = JSONLDRelatedField(serializer='EventSerializer', required=False, view_name='event-detail',
                                     queryset=Event.objects.all(), allow_null=True)
    event_status = EnumChoiceField(Event.STATUSES, required=False)
    publication_status = EnumChoiceField(PUBLICATION_STATUSES, required=False)
    external_links = EventLinkSerializer(many=True, required=False)
    offers = OfferSerializer(many=True, required=False)
    data_source = serializers.PrimaryKeyRelatedField(queryset=DataSource.objects.all(),
                                                     required=False)
    publisher = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all(),
                                                   required=False)
    sub_events = JSONLDRelatedField(serializer='EventSerializer',
                                    required=False, view_name='event-detail',
                                    many=True, queryset=Event.objects.filter(deleted=False))
    images = JSONLDRelatedField(serializer=ImageSerializer, required=False, allow_null=True, many=True,
                                view_name='image-detail', queryset=Image.objects.all(), expanded=True)
    videos = VideoSerializer(many=True, required=False)
    in_language = JSONLDRelatedField(serializer=LanguageSerializer, required=False,
                                     view_name='language-detail', many=True, queryset=Language.objects.all())
    audience = JSONLDRelatedField(serializer=KeywordSerializer, view_name='keyword-detail',
                                  many=True, required=False, queryset=Keyword.objects.filter(deprecated=False))

    view_name = 'event-detail'
    fields_needed_to_publish = ('keywords', 'location', 'start_time', 'short_description')
    created_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)
    last_modified_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)
    date_published = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)
    start_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)
    end_time = DateTimeField(default_timezone=pytz.UTC, required=False, allow_null=True)
    created_by = serializers.StringRelatedField(required=False, allow_null=True)
    last_modified_by = serializers.StringRelatedField(required=False, allow_null=True)
    is_virtualevent = serializers.BooleanField(required=False, allow_null=False)

    def __init__(self, *args, skip_empties=False, **kwargs):
        super(EventSerializer, self).__init__(*args, **kwargs)
        # The following can be used when serializing when
        # testing and debugging.
        self.skip_empties = skip_empties

        if self.context:
            for ext in self.context.get('extensions', ()):
                self.fields['extension_{}'.format(ext.identifier)] = ext.get_extension_serializer()

    def parse_datetimes(self, data):
        # here, we also set has_start_time and has_end_time accordingly
        for field in ['date_published', 'start_time', 'end_time']:
            val = data.get(field, None)
            if val:
                if isinstance(val, str):
                    data[field], data['has_' + field] = utils.parse_time(val, not field == 'end_time')
        return data

    def to_internal_value(self, data):
        data = self.parse_datetimes(data)
        data = super().to_internal_value(data)
        return data

    def validate(self, data):
        # clean all text fields, only description may contain any html
        data = clean_text_fields(data, allowed_html_fields=['description'])

        data = super().validate(data)

        if 'publication_status' not in data:
            data['publication_status'] = PublicationStatus.PUBLIC

        # if the event is a draft, postponed or cancelled, no further validation is performed
        if (data['publication_status'] == PublicationStatus.DRAFT or
                data.get('event_status', None) == Event.Status.CANCELLED or
                (self.context['request'].method == 'PUT' and 'start_time' in data and not data['start_time'])):
            data = self.run_extension_validations(data)
            return data

        if (data['is_virtualevent'] == True):
            self.fields_needed_to_publish = list(self.fields_needed_to_publish)
            self.fields_needed_to_publish.remove('location')
            self.fields_needed_to_publish.append('virtualevent_url')
            self.fields_needed_to_publish = tuple(self.fields_needed_to_publish)

        if 'super_event_type' in data:
            if data['super_event_type'] == 'recurring':
                self.fields_needed_to_publish = list (self.fields_needed_to_publish)
                self.fields_needed_to_publish.remove('start_time')
                self.fields_needed_to_publish = tuple(self.fields_needed_to_publish)
            
        # check that published events have a location, keyword and start_time
        languages = utils.get_fixed_lang_codes()

        errors = {}
        lang_error_msg = _('This field must be specified before an event is published.')
        for field in self.fields_needed_to_publish:
            if field in self.translated_fields:
                for lang in languages:
                    name = "name_%s" % lang
                    field_lang = "%s_%s" % (field, lang)
                    if data.get(name) and not data.get(field_lang):
                        errors.setdefault(field, {})[lang] = lang_error_msg
                    if data.get(field_lang) and field == 'short_description' and len(data.get(field_lang, [])) > 160:
                        errors.setdefault(field, {})[lang] = (
                            _('Short description length must be 160 characters or less'))

            elif not data.get(field):
                errors[field] = lang_error_msg

        # published events need price info = at least one offer that is free or not
        offer_exists = False
        for index, offer in enumerate(data.get('offers', [])):
            if 'is_free' in offer:
                offer_exists = True
            # clean offer text fields
            data['offers'][index] = clean_text_fields(offer)

        if not offer_exists:
            errors['offers'] = _('Price info must be specified before an event is published.')

        # clean link description text
        for index, link in enumerate(data.get('external_links', [])):
            # clean link text fields
            data['external_links'][index] = clean_text_fields(link)

        # clean video text fields
        for index, video in enumerate(data.get('video', [])):
            # clean link text fields
            data['video'][index] = clean_text_fields(video)

        # If no end timestamp supplied, we treat the event as ending at midnight
        if not data.get('end_time'):
            # The start time may also be null if the event is postponed
            if not data.get('start_time'):
                data['has_end_time'] = False
                data['end_time'] = None
            else:
                data['has_end_time'] = False
                data['end_time'] = timezone.localtime(data['start_time'])\
                    .replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
                data['end_time'] += timedelta(days=1)

        if data.get('end_time') and data['end_time'] < timezone.now():
            errors['end_time'] = force_text(_('End time cannot be in the past. Please set a future end time.'))

        if errors:
            raise serializers.ValidationError(errors)

        data = self.run_extension_validations(data)

        return data

    def run_extension_validations(self, data):
        for ext in self.context.get('extensions', ()):
            new_data = ext.validate_event_data(self, data)
            if new_data:
                data = new_data
        return data

    def create(self, validated_data):
        # if id was not provided, we generate it upon creation:
        if 'id' not in validated_data:
            validated_data['id'] = generate_id(self.data_source)

        if 'location' not in validated_data:
            try:
                validated_data['location'] = Place.objects.get(id='virtual:public')
            except (Place.DoesNotExist, Place.MultipleObjectsReturned):
                print(f'Attempted to create event with default location')

        offers = validated_data.pop('offers', [])
        links = validated_data.pop('external_links', [])
        videos = validated_data.pop('videos', [])

        validated_data.update({'created_by': self.user,
                               'last_modified_by': self.user,
                               'created_time': Event.now(),  # we must specify creation time as we are setting id
                               'event_status': Event.Status.SCHEDULED,  # mark all newly created events as scheduled
                               })

        # pop out extension related fields because create() cannot stand them
        original_validated_data = deepcopy(validated_data)
        for field_name, field in self.fields.items():
            if field_name.startswith('extension_') and field.source in validated_data:
                validated_data.pop(field.source)

        event = super().create(validated_data)

        # create and add related objects
        for offer in offers:
            Offer.objects.create(event=event, **offer)
        for link in links:
            EventLink.objects.create(event=event, **link)
        for video in videos:
            Video.objects.create(event=event, **video)

        request = self.context['request']
        extensions = get_extensions_from_request(request)

        for ext in extensions:
            ext.post_create_event(request=request, event=event, data=original_validated_data)

        post_save(event)

        return event

    def update(self, instance, validated_data):
        offers = validated_data.pop('offers', None)
        links = validated_data.pop('external_links', None)
        videos = validated_data.pop('videos', None)

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

        # pop out extension related fields because update() cannot stand them
        original_validated_data = deepcopy(validated_data)
        for field_name, field in self.fields.items():
            if field_name.startswith('extension_') and field.source in validated_data:
                validated_data.pop(field.source)

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

        # update videos
        if isinstance(videos, list):
            instance.videos.all().delete()
            for video in videos:
                Video.objects.create(event=instance, **video)

        request = self.context['request']
        extensions = get_extensions_from_request(request)

        for ext in extensions:
            ext.post_update_event(request=request, event=instance, data=original_validated_data)

        post_update(instance)

        return instance

    def to_representation(self, obj):
        ret = super(EventSerializer, self).to_representation(obj)

        if obj.deleted:
            keys_to_preserve = ['id', 'name', 'last_modified_time', 'deleted', 'replaced_by']
            for key in ret.keys() - keys_to_preserve:
                del ret[key]
            ret['name'] = utils.get_deleted_object_name()
            return ret

        if self.context['request'].accepted_renderer.format == 'docx':
            ret['end_time_obj'] = obj.end_time
            ret['start_time_obj'] = obj.start_time
            ret['location'] = obj.location

        if obj.start_time and not obj.has_start_time:
            # Return only the date part
            ret['start_time'] = obj.start_time.astimezone(LOCAL_TZ).strftime('%Y-%m-%d')
        if obj.end_time and not obj.has_end_time:
            # If we're storing only the date part, do not pretend we have the exact time.
            # Timestamp is of the form %Y-%m-%dT00:00:00, so we report the previous date.
            ret['end_time'] = (obj.end_time - timedelta(days=1)).astimezone(LOCAL_TZ).strftime('%Y-%m-%d')
            # Unless the event is short, then no need for end time
            if obj.start_time and obj.end_time - obj.start_time <= timedelta(days=1):
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
        request = self.context.get('request')
        if request:
            if not request.user.is_authenticated:
                del ret['publication_status']

        if ret['sub_events']:
            sub_events_relation = self.fields['sub_events'].child_relation
            undeleted_sub_events = []
            for sub_event in obj.sub_events.filter(deleted=False):
                undeleted_sub_events.append(sub_events_relation.to_representation(sub_event))
            ret['sub_events'] = undeleted_sub_events

        return ret

    class Meta:
        model = Event
        exclude = ()
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


class LinkedEventsOrderingFilter(filters.OrderingFilter):
    ordering_param = 'sort'


class EventOrderingFilter(LinkedEventsOrderingFilter):
    def filter_queryset(self, request, queryset, view):
        queryset = super(EventOrderingFilter, self).filter_queryset(request, queryset, view)
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            ordering = []
        if 'duration' in ordering:
            queryset = queryset.extra(select={'duration': 'end_time - start_time'})
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
        qset = Q()
        for field in fields:
            # check all languages for each field
            qset |= _text_qset_by_translated_field(field, val)
        queryset = queryset.filter(qset)

    val = params.get('last_modified_since', None)
    # This should be in format which dateutil.parser recognizes, e.g.
    # 2014-10-29T12:00:00Z == 2014-10-29T12:00:00+0000 (UTC time)
    # or 2014-10-29T12:00:00+0200 (local time)
    if val:
        dt = utils.parse_time(val, is_start=False)[0]
        queryset = queryset.filter(Q(last_modified_time__gte=dt))

    start = params.get('start')
    end = params.get('end')
    days = params.get('days')

    if days:
        try:
            days = int(days)
        except ValueError:
            raise ParseError(_('Error while parsing days.'))
        if days < 1:
            raise serializers.ValidationError(_('Days must be 1 or more.'))

        if start or end:
            raise serializers.ValidationError(_('Start or end cannot be used with days.'))

        today = datetime.now(timezone.utc).date()

        start = today.isoformat()
        end = (today + timedelta(days=days)).isoformat()

    if not end:
        # postponed events are considered to be "far" in the future and should be included if end is *not* given
        postponed_Q = Q(event_status=Event.Status.POSTPONED)
    else:
        postponed_Q = Q()

    if start:
        dt = utils.parse_time(start, is_start=True)[0]
        # only return events with specified end times, or unspecified start times, during the whole of the event
        # this gets of rid pesky one-day events with no known end time (but known start) after they started
        queryset = queryset.filter(Q(end_time__gt=dt, has_end_time=True) |
                                   Q(end_time__gt=dt, has_start_time=False) |
                                   Q(start_time__gte=dt) |
                                   postponed_Q)

    if end:
        dt = utils.parse_time(end, is_start=False)[0]
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
        try:
            # replaced keywords are looked up for backwards compatibility
            val = [getattr(Keyword.objects.get(id=kid).replaced_by, 'id', None) or kid for kid in val]
        except Keyword.DoesNotExist:
            # the user asked for an unknown keyword
            queryset = queryset.none()
        queryset = queryset.filter(Q(keywords__pk__in=val) | Q(audience__pk__in=val)).distinct()

    # 'keyword_OR' behaves the same way as 'keyword'
    val = params.get('keyword_OR', None)
    if val:
        val = val.split(',')
        try:
            # replaced keywords are looked up for backwards compatibility
            val = [getattr(Keyword.objects.get(id=kid).replaced_by, 'id', None) or kid for kid in val]
        except Keyword.DoesNotExist:
            # the user asked for an unknown keyword
            queryset = queryset.none()
        queryset = queryset.filter(Q(keywords__pk__in=val) | Q(audience__pk__in=val)).distinct()

    # Filter by keyword ids requiring all keywords to be present in event
    val = params.get('keyword_AND', None)
    if val:
        val = val.split(',')
        for keyword_id in val:
            try:
                # replaced keywords are looked up for backwards compatibility
                val = getattr(Keyword.objects.get(id=keyword_id).replaced_by, 'id', None) or keyword_id
            except Keyword.DoesNotExist:
                # the user asked for an unknown keyword
                queryset = queryset.none()
            queryset = queryset.filter(Q(keywords__pk=keyword_id) | Q(audience__pk=keyword_id))
        queryset = queryset.distinct()

    # Negative filter for keyword ids
    val = params.get('keyword!', None)
    if val:
        val = val.split(',')
        try:
            # replaced keywords are looked up for backwards compatibility
            val = [getattr(Keyword.objects.get(id=kid).replaced_by, 'id', None) or kid for kid in val]
        except Keyword.DoesNotExist:
            # the user asked for an unknown keyword
            pass
        queryset = queryset.exclude(Q(keywords__pk__in=val) | Q(audience__pk__in=val)).distinct()

    # filter only super or non-super events. to be deprecated?
    val = params.get('recurring', None)
    if val:
        val = val.lower()
        if val == 'super':
            # same as ?super_event_type=recurring
            queryset = queryset.filter(super_event_type=Event.SuperEventType.RECURRING)
        elif val == 'sub':
            # same as ?super_event_type=none,umbrella, weirdly yielding non-sub events too.
            # don't know if users want this to remain tho. do we want that or is there a need
            # to change this to actually filter only subevents of recurring events?
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
        q = get_publisher_query(val)
        queryset = queryset.filter(q)

    # Filter by publisher ancestors, multiple ids separated by comma
    val = params.get('publisher_ancestor', None)
    if val:
        val = val.split(',')
        ancestors = Organization.objects.filter(id__in=val)

        # Get ids of ancestors and all their descendants
        publishers = Organization.objects.none()
        for org in ancestors.all():
            publishers |= org.get_descendants(include_self=True)
        publisher_ids = [org['id'] for org in publishers.all().values('id')]

        q = get_publisher_query(publisher_ids)
        queryset = queryset.filter(q)

    # Filter by publication status
    val = params.get('publication_status', None)
    if val == 'draft':
        queryset = queryset.filter(publication_status=PublicationStatus.DRAFT)
    elif val == 'public':
        queryset = queryset.filter(publication_status=PublicationStatus.PUBLIC)

    # Filter by event status
    val = params.get('event_status', None)
    if val and val.lower() == 'eventscheduled':
        queryset = queryset.filter(event_status=Event.Status.SCHEDULED)
    elif val and val.lower() == 'eventrescheduled':
        queryset = queryset.filter(event_status=Event.Status.RESCHEDULED)
    elif val and val.lower() == 'eventcancelled':
        queryset = queryset.filter(event_status=Event.Status.CANCELLED)
    elif val and val.lower() == 'eventpostponed':
        queryset = queryset.filter(event_status=Event.Status.POSTPONED)

    # Filter by language, checking both string content and in_language field
    val = params.get('language', None)
    if val:
        val = val.split(',')
        q = Q()
        for lang in val:
            if lang in utils.get_fixed_lang_codes():
                # check string content if language has translations available
                name_arg = {'name_' + lang + '__isnull': False}
                desc_arg = {'description_' + lang + '__isnull': False}
                short_desc_arg = {'short_description_' + lang + '__isnull': False}
                q = q | Q(in_language__id=lang) | Q(**name_arg) | Q(**desc_arg) | Q(**short_desc_arg)
            else:
                q = q | Q(in_language__id=lang)
        queryset = queryset.filter(q)

    # Filter by in_language field only
    val = params.get('in_language', None)
    if val:
        val = val.split(',')
        q = Q()
        for lang in val:
            q = q | Q(in_language__id=lang)
        queryset = queryset.filter(q)

    # Filter by translation only
    val = params.get('translation', None)
    if val:
        val = val.split(',')
        q = Q()
        for lang in val:
            if lang in utils.get_fixed_lang_codes():
                # check string content if language has translations available
                name_arg = {'name_' + lang + '__isnull': False}
                desc_arg = {'description_' + lang + '__isnull': False}
                short_desc_arg = {'short_description_' + lang + '__isnull': False}
                q = q | Q(**name_arg) | Q(**desc_arg) | Q(**short_desc_arg)
            else:
                # language has no translations, matching condition must be false
                q = q | Q(pk__in=[])
        queryset = queryset.filter(q)

    # Filter by audience min age
    val = params.get('audience_min_age', None)
    if val:
        try:
            min_age = int(val)
        except ValueError:
            raise ParseError(_('Audience minimum age must be a digit.'))
        queryset = queryset.filter(audience_min_age__lte=min_age)

    # Filter by audience max age
    val = params.get('audience_max_age', None)
    if val:
        try:
            max_age = int(val)
        except ValueError:
            raise ParseError(_('Audience maximum age must be a digit.'))
        queryset = queryset.filter(audience_max_age__gte=max_age)

    # Filter deleted events
    val = params.get('show_deleted', None)
    # ONLY deleted events (for cache updates etc., returns deleted object ids)
    val_deleted = params.get('deleted', None)
    if not val and not val_deleted:
        queryset = queryset.filter(deleted=False)
    if val_deleted:
        queryset = queryset.filter(deleted=True)

    # Filter by free offer
    val = params.get('is_free', None)
    if val and val.lower() in ['true', 'false']:
        if val.lower() == 'true':
            queryset = queryset.filter(offers__is_free=True)
        elif val.lower() == 'false':
            queryset = queryset.exclude(offers__is_free=True)

    return queryset


class EventExtensionFilterBackend(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        extensions = get_extensions_from_request(request)

        for ext in extensions:
            queryset = ext.filter_event_queryset(request, queryset, view)

        return queryset


def in_or_null_filter(field_name, queryset, name, value):
    # supports filtering objects by several values in the same field; null or none will trigger isnull filter
    q = Q()
    if 'null' in value or 'none' in value:
        null_query = {field_name + '__isnull': True}
        q = q | Q(**null_query)
        if 'null' in value:
            value.remove('null')
        if 'none' in value:
            value.remove('none')
    if value:
        in_query = {field_name + '__in': value}
        q = q | Q(**in_query)
    return queryset.filter(q)


class EventFilter(django_filters.rest_framework.FilterSet):
    division = django_filters.Filter(field_name='location__divisions',
                                     widget=django_filters.widgets.CSVWidget(),
                                     method=filter_division)
    super_event_type = django_filters.Filter(field_name='super_event_type',
                                             widget=django_filters.widgets.CSVWidget(),
                                             method=partial(in_or_null_filter, 'super_event_type'))
    super_event = django_filters.Filter(field_name='super_event',
                                        widget=django_filters.widgets.CSVWidget(),
                                        method=partial(in_or_null_filter, 'super_event'))

    class Meta:
        model = Event
        fields = ('division', 'super_event_type', 'super_event')


class EventDeletedException(APIException):
    status_code = 410
    default_detail = 'Event has been deleted.'
    default_code = 'gone'


class EventViewSet(JSONAPIViewMixin, BulkModelViewSet, viewsets.ReadOnlyModelViewSet):
    queryset = Event.objects.all()
    # This exclude is, atm, a bit overkill, considering it causes a massive query and no such events exist.
    # queryset = queryset.exclude(super_event_type=Event.SuperEventType.RECURRING, sub_events=None)
    # Use select_ and prefetch_related() to reduce the amount of queries
    queryset = queryset.select_related('location', 'publisher')
    queryset = queryset.prefetch_related(
        'offers', 'keywords', 'audience', 'images', 'images__publisher', 'external_links', 'sub_events', 'in_language',
        'videos')
    serializer_class = EventSerializer
    filter_backends = (EventOrderingFilter, django_filters.rest_framework.DjangoFilterBackend,
                       EventExtensionFilterBackend)
    filterset_class = EventFilter
    ordering_fields = ('start_time', 'end_time', 'duration', 'last_modified_time', 'name')
    ordering = ('-last_modified_time',)
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [DOCXRenderer]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_source = None
        self.organization = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.data_source, self.organization = get_authenticated_data_source_and_publisher(request)

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
        context['extensions'] = get_extensions_from_request(self.request)
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        context = self.get_serializer_context()
        # prefetch extra if the user want them included
        if 'include' in context:
            for included in context['include']:
                if included == 'location':
                    queryset = queryset.prefetch_related('location__divisions',
                                                         'location__divisions__type',
                                                         'location__divisions__municipality')
                if included == 'keywords':
                    queryset = queryset.prefetch_related('keywords__alt_labels',
                                                         'audience__alt_labels')
        return apply_select_and_prefetch(
            queryset=queryset,
            extensions=get_extensions_from_request(self.request)
        )

    def get_object(self):
        # Overridden to prevent queryset filtering from being applied
        # outside list views.
        try:
            event = Event.objects.get(pk=self.kwargs['pk'])
        except Event.DoesNotExist:
            raise Http404("Event does not exist")
        if (
            event.publication_status == PublicationStatus.PUBLIC or
            self.request.user.is_authenticated and
            self.request.user.can_edit_event(event.publisher, event.publication_status)
        ):
            if event.deleted:
                raise EventDeletedException()
            return event
        else:
            raise Http404("Event does not exist")

    def filter_queryset(self, queryset):
        """
        TODO: convert to use proper filter framework
        """
        original_queryset = super(EventViewSet, self).filter_queryset(queryset)

        if self.request.method in SAFE_METHODS:
            # we cannot use distinct for performance reasons
            public_queryset = original_queryset.filter(publication_status=PublicationStatus.PUBLIC)
            editable_queryset = original_queryset.none()
            if self.request.user.is_authenticated:
                editable_queryset = self.request.user.get_editable_events(original_queryset)
            # by default, only public events are shown in the event list
            queryset = public_queryset
            # however, certain query parameters allow customizing the listing for authenticated users
            show_all = self.request.query_params.get('show_all')
            if show_all:
                # displays all editable events, including drafts, and public non-editable events
                queryset = editable_queryset | public_queryset
            admin_user = self.request.query_params.get('admin_user')
            if admin_user:
                # displays all editable events, including drafts, but no other public events
                queryset = editable_queryset
            created_by = self.request.query_params.get('created_by')
            if created_by:
                # only displays events by the particular user
                if self.request.user.is_authenticated:
                    queryset = queryset.filter(created_by=self.request.user)
                else:
                    queryset = queryset.none()
        else:
            # prevent changing events user does not have write permissions (for bulk operations)
            queryset = self.request.user.get_editable_events(original_queryset)

        queryset = _filter_event_queryset(queryset, self.request.query_params,
                                          srs=self.srs)
        return queryset.filter()

    def allow_bulk_destroy(self, qs, filtered):
        return False

    def update(self, *args, **kwargs):
        response = super().update(*args, **kwargs)
        original_event = Event.objects.get(id=response.data['id'])
        if original_event.replaced_by is not None:
            replacing_event = original_event.replaced_by
            context = self.get_serializer_context()
            response.data = EventSerializer(replacing_event, context=context).data
        return response

    def perform_update(self, serializer):
        # Prevent changing an event that user does not have write permissions
        # For bulk update, the editable queryset is filtered in filter_queryset
        # method
        if isinstance(serializer, EventSerializer) and not self.request.user.can_edit_event(
                serializer.instance.publisher,
                serializer.instance.publication_status,
        ):
            raise DRFPermissionDenied()

        # Prevent changing existing events to a state that user doe snot have write permissions
        if isinstance(serializer.validated_data, list):
            event_data_list = serializer.validated_data
        else:
            event_data_list = [serializer.validated_data]

        for event_data in event_data_list:
            org = self.organization
            if hasattr(event_data, 'publisher'):
                org = event_data['publisher']
            if not self.request.user.can_edit_event(org, event_data['publication_status']):
                raise DRFPermissionDenied()

        super().perform_update(serializer)

    @atomic
    def bulk_update(self, request, *args, **kwargs):
        return super().bulk_update(request, *args, **kwargs)

    @atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        if isinstance(serializer.validated_data, list):
            event_data_list = serializer.validated_data
        else:
            event_data_list = [serializer.validated_data]

        for event_data in event_data_list:
            org = self.organization
            if hasattr(event_data, 'publisher'):
                org = event_data['publisher']
            if not self.request.user.can_edit_event(org, event_data['publication_status']):
                raise DRFPermissionDenied()

        super().perform_create(serializer)

    @atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if not self.request.user.can_edit_event(instance.publisher, instance.publication_status):
            raise DRFPermissionDenied()
        instance.soft_delete()

    def retrieve(self, request, *args, **kwargs):
        try:
            event = Event.objects.get(pk=kwargs['pk'])
        except Event.DoesNotExist:
            raise Http404()
        if event.replaced_by:
            event = event.get_replacement()
            return HttpResponsePermanentRedirect(reverse('event-detail',
                                                         kwargs={'pk': event.pk},
                                                         request=request))
        return super().retrieve(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        # docx renderer has additional requirements for listing events
        if request.accepted_renderer.format == 'docx':
            if not request.query_params.get('location'):
                raise ParseError(
                    {'detail': _('Must specify a location when fetching DOCX file.')})
            queryset = self.filter_queryset(self.get_queryset())
            if queryset.count() == 0:
                raise ParseError({'detail': _('No events.')})
            if len(set([event.location for event in queryset])) > 1:
                raise ParseError({'detail': _('Only one location allowed.')})
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        # Switch to normal renderer for docx errors.
        response = super().finalize_response(request, response, *args, **kwargs)
        # Prevent rendering errors as DOCX files
        if response.status_code != 200 and request.accepted_renderer.format == 'docx':
            first_renderer = self.renderer_classes[0]()
            response.accepted_renderer = first_renderer
            response.accepted_media_type = first_renderer.media_type

        return response


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


class SearchViewSet(JSONAPIViewMixin, GeoModelAPIView, viewsets.ViewSetMixin, generics.ListAPIView):
    def get_serializer_class(self):
        if self.request.version == 'v0.1':
            return SearchSerializerV0_1
        return SearchSerializer

    def list(self, request, *args, **kwargs):
        languages = utils.get_fixed_lang_codes()

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
            division = params.get('division', None)
            if division:
                queryset = filter_division(queryset, 'location__divisions', division)

            start = params.get('start', None)
            if start:
                dt = utils.parse_time(start, is_start=True)[0]
                queryset = queryset.filter(Q(end_time__gt=dt) | Q(start_time__gte=dt))

            end = params.get('end', None)
            if end:
                dt = utils.parse_time(end, is_start=False)[0]
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

        if len(models) == 1 and Place in models:
            division = params.get('division', None)
            if division:
                queryset = filter_division(queryset, 'divisions', division)

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


register_view(SearchViewSet, 'search', basename='search')
