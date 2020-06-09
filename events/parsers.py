import json
from events import renderers
from rest_framework.parsers import JSONParser, ParseError
from events import utils
from django.conf import settings
from django.utils import six


def rename_fields(dataz):
    if isinstance(dataz, dict):
        new_data = dict()
        for key, value in dataz.items():
            newkey = utils.convert_from_camelcase(key)
            if isinstance(value, (dict, list)):
                new_data[newkey] = rename_fields(value)
            else:
                new_data[newkey] = value
        return new_data
    elif isinstance(dataz, (list, tuple)):
        new_data = []
        for value in dataz:
            if isinstance(value, (dict, list, tuple)):
                new_data.append(rename_fields(value))
            else:
                new_data.append(value)
        return new_data


class CamelCaseJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        if 'disable_camelcase' in parser_context['request'].query_params:
            return super(CamelCaseJSONParser, self).parse(media_type,
                                                          parser_context)
        else:
            encoding = parser_context.get('encoding', settings.DEFAULT_CHARSET)
            try:
                data = stream.read().decode(encoding)
                return rename_fields(json.loads(data))
            except ValueError as exc:
                raise ParseError('JSON parse error - %s' % (exc))


class JSONLDParser(CamelCaseJSONParser):
    media_type = 'application/ld+json'
    renderer_class = renderers.JSONLDRenderer
