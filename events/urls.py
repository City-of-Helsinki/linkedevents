from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter
from events import api


router = DefaultRouter()
for view in api.all_views:
    kwargs = {}
    if 'base_name' in view:
        kwargs['base_name'] = view['base_name']
    router.register(view['name'], view['class'], **kwargs)

urlpatterns = [
    url(r'^', include(router.urls)),
]
