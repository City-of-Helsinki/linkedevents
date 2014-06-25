from django.conf.urls import patterns, include, url
from events.routers import DocumentedRouter
from events import api


router = DocumentedRouter()
for view in api.all_views:
    kwargs = {}
    if 'base_name' in view:
        kwargs['base_name'] = view['base_name']
    router.register(view['name'], view['class'], **kwargs)

urlpatterns = patterns('',
    url(r'^', include(router.urls)),
)
