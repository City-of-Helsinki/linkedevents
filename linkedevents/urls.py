from django.core.urlresolvers import reverse
from django.conf.urls import url, include
from django.views.generic import RedirectView

from .api import LinkedEventsAPIRouter

from django.contrib import admin
admin.autodiscover()

api_router = LinkedEventsAPIRouter()


class RedirectToAPIRootView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse('api-root', kwargs={'version': 'v1'})

urlpatterns = [
    url(r'^(?P<version>(v0.1|v1))/', include(api_router.urls)),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^accounts/', include('allauth.urls')),
    url(r'^$', RedirectToAPIRootView.as_view()),
]
