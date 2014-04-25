from django.conf.urls import patterns, include, url
from events.routers import DocumentedRouter
from events import api

router = DocumentedRouter()
for view in api.all_views:
    router.register(view['name'], view['class'])

urlpatterns = patterns('',
    url(r'^', include(router.urls)),
)
