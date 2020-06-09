from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter
from events import api


router = DefaultRouter()
for view in api.all_views:
    kwargs = {}
    if 'basename' in view:
        kwargs['basename'] = view['basename']
    router.register(view['name'], view['class'], **kwargs)

urlpatterns = [
    url(r'^', include(router.urls)),
]
