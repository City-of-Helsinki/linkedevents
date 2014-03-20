from rest_framework.renderers import JSONRenderer


class JSONLDRenderer(JSONRenderer):
    media_type = 'application/ld+json'
    format = 'json-ld'
