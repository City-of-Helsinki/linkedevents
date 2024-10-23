from django.utils.translation import gettext_lazy as _
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.utils import OpenApiTypes, extend_schema_field, inline_serializer
from isodate import Duration, duration_isoformat, parse_duration
from parler import appsettings as parler_appsettings
from rest_framework import serializers
from rest_framework.exceptions import ParseError

from events import utils
from helevents.models import User
from helevents.serializers import UserSerializer
from linkedevents.fields import JSONLDRelatedField


@extend_schema_field(
    inline_serializer(
        name="EventJSONLDRelatedFieldSerializer",
        fields={
            "@id": serializers.URLField(
                default="https://api.url/v1/event/example:example/"
            ),
        },
    )
)
class EventJSONLDRelatedField(JSONLDRelatedField):
    pass


@extend_schema_field(
    inline_serializer(
        name="EventsJSONLDRelatedFieldSerializer",
        fields={
            "@id": serializers.URLField(
                default="https://api.url/v1/event/example:example/"
            ),
        },
        many=True,
    )
)
class EventsJSONLDRelatedField(JSONLDRelatedField):
    pass


@extend_schema_field(
    inline_serializer(
        name="ImagesJSONLDRelatedFieldSerializer",
        fields={
            "@id": serializers.URLField(
                default="https://api.url/v1/image/example:example/"
            ),
        },
        many=True,
    )
)
class ImagesJSONLDRelatedField(JSONLDRelatedField):
    pass


@extend_schema_field(
    inline_serializer(
        name="KeywordsJSONLDRelatedFieldSerializer",
        fields={
            "@id": serializers.URLField(
                default="https://api.url/v1/keyword/example:example/"
            ),
        },
        many=True,
    )
)
class KeywordsJSONLDRelatedField(JSONLDRelatedField):
    pass


@extend_schema_field(
    inline_serializer(
        name="LanguagesJSONLDRelatedFieldSerializer",
        fields={
            "@id": serializers.URLField(default="https://api.url/v1/language/fi/"),
        },
        many=True,
    )
)
class LanguagesJSONLDRelatedField(JSONLDRelatedField):
    pass


@extend_schema_field(
    inline_serializer(
        name="PlaceJSONLDRelatedFieldSerializer",
        fields={
            "@id": serializers.URLField(
                default="https://api.url/v1/place/example:example/"
            ),
        },
    )
)
class LocationJSONLDRelatedField(JSONLDRelatedField):
    pass


@extend_schema_field(
    inline_serializer(
        name="RegistrationJSONLDRelatedFieldSerializer",
        fields={
            "@id": serializers.URLField(default="https://api.url/v1/registration/1/"),
        },
    )
)
class RegistrationJSONLDRelatedField(JSONLDRelatedField):
    pass


@extend_schema_field(OpenApiTypes.STR)
class EnumChoiceField(serializers.Field):
    """
    Database value of tinyint is converted to and from a string representation
    of choice field.
    """

    def __init__(self, choices, prefix="", **kwargs):
        self.choices = choices
        self.prefix = prefix
        super().__init__(**kwargs)

    def to_representation(self, obj):
        if obj is None:
            return None
        return self.prefix + str(utils.get_value_from_tuple_list(self.choices, obj, 1))

    def to_internal_value(self, data):
        value = utils.get_value_from_tuple_list(
            self.choices, self.prefix + str(data), 0
        )
        if value is None:
            raise ParseError(_(f'Invalid value "{data}"'))
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


class OrganizationUserField(serializers.SlugRelatedField):
    def __init__(self, **kwargs):
        super().__init__(queryset=User.objects.all(), slug_field="username", **kwargs)

    def to_representation(self, obj):
        return UserSerializer(obj).data


@extend_schema_field(OpenApiTypes.STR)
class StringSlugRelatedField(serializers.SlugRelatedField):
    pass


class TranslationsFieldExtension(OpenApiSerializerFieldExtension):
    target_class = "parler_rest.fields.TranslatedFieldsField"

    def map_serializer_field(self, auto_schema, direction):
        translation_serializer = self.target.serializer_class
        translation_component = auto_schema.resolve_serializer(
            translation_serializer, direction
        )

        return {
            "type": "object",
            "properties": {
                parler_appsettings.PARLER_LANGUAGES["default"][
                    "code"
                ]: translation_component.ref,
            },
        }
