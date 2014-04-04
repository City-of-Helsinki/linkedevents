from rest_framework import renderers


class JSONRenderer(renderers.JSONRenderer):
    charset = 'utf-8'
    def render(self, data, media_type=None, renderer_context=None):
        return super(JSONRenderer, self).render(data, media_type,
                                                renderer_context)


class JSONLDRenderer(JSONRenderer):
    media_type = 'application/ld+json'
    format = 'json-ld'
    charset = 'utf-8'
