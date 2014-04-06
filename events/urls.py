from django.conf.urls import patterns, include, url
from rest_framework import routers
from events import api

router = routers.DefaultRouter()
for view in api.all_views:
    router.register(view['name'], view['class'])

urlpatterns = patterns('',
    url(r'^', include(router.urls)),
)
