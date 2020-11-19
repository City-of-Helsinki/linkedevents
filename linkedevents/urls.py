import debug_toolbar
import environ
from django.conf.urls import include, url
from django.contrib import admin
from django.urls import reverse
from django.views.generic import RedirectView

from .api import LinkedEventsAPIRouter

api_router = LinkedEventsAPIRouter()
env = environ.Env(DEBUG=(bool, False))


class RedirectToAPIRootView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse('api-root', kwargs={'version': 'v1'})


urlpatterns = [
    url(r'^(?P<version>(v0.1|v1))/', include(api_router.urls)),
    url(r'^admin/', admin.site.urls),
    url(r'^accounts/', include('allauth.urls')),
    url(r'^$', RedirectToAPIRootView.as_view()),
]

if env('DEBUG'):
    urlpatterns.append(url(r'^__debug__/', include(debug_toolbar.urls)))
