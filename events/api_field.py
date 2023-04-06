from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ParseError

from events import utils


class EnumChoiceField(serializers.Field):
    """
    Database value of tinyint is converted to and from a string representation
    of choice field.

    TODO: Find if there's standardized way to render Schema.org enumeration
    instances in JSON-LD.
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
