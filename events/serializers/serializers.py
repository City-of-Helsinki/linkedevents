from __future__ import unicode_literals

from rest_framework import serializers

from events.models import *
from fields import TranslatedField
from django.conf import settings
from itertools import chain


class TranslationAwareSerializer(serializers.HyperlinkedModelSerializer):
    name = TranslatedField()
    description = TranslatedField()

    class Meta:
        exclude = list(
            chain.from_iterable((('name_' + code, 'description_' + code)
                                 for code, _ in settings.LANGUAGES))
        )


class EventSerializer(TranslationAwareSerializer):
    class Meta(TranslationAwareSerializer.Meta):
        model = Event


class CategorySerializer(TranslationAwareSerializer):
    class Meta(TranslationAwareSerializer.Meta):
        model = EventCategory


class PlaceSerializer(TranslationAwareSerializer):
    class Meta(TranslationAwareSerializer.Meta):
        model = Place


class OrganizationSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(TranslationAwareSerializer.Meta):
        model = Organization


class LanguageSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(TranslationAwareSerializer.Meta):
        model = Language