from django.conf.urls import url, include
from django.views.generic import RedirectView

from .api import LinkedEventsAPIRouter

from django.contrib import admin
admin.autodiscover()

api_router = LinkedEventsAPIRouter()


urlpatterns = [
    url(r'^v0.1/', include(api_router.urls)),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^accounts/', include('allauth.urls')),
    url(r'^$', RedirectView.as_view(url='/v0.1/', permanent=False)),
    url(r'^v1', RedirectView.as_view(url='/v0.1/', permanent=False)),
]
