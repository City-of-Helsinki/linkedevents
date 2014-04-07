from django.conf.urls import *
from django.views.generic import RedirectView

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^v0.1/', include('events.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^docs/', include('rest_framework_swagger.urls')),
    url(r'^$', RedirectView.as_view(url='/v0.1/', permanent=False)),
    url(r'^v1', RedirectView.as_view(url='/v0.1/', permanent=False)),
)
