from django.conf.urls import url, include
from django.views.generic import RedirectView

from django.contrib import admin
admin.autodiscover()

urlpatterns = [
    url(r'^v0.1/', include('events.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^$', RedirectView.as_view(url='/v0.1/', permanent=False)),
    url(r'^v1', RedirectView.as_view(url='/v0.1/', permanent=False)),
]
