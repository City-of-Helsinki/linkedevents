from rest_framework.renderers import UnicodeJSONRenderer


class JSONLDRenderer(UnicodeJSONRenderer):
    media_type = ' application/ld+json'
    format = 'json-ld'