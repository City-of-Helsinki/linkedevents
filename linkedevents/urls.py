from django.urls import reverse
from django.conf.urls import url, include
from django.views.generic import RedirectView

from .api import LinkedEventsAPIRouter
from django.contrib import admin
from massadmin.massadmin import mass_change_view

api_router = LinkedEventsAPIRouter()


class RedirectToAPIRootView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse('api-root', kwargs={'version': 'v1'})


urlpatterns = [
    url(r'^(?P<version>(v0.1|v1))/', include(api_router.urls)),
    url(r'^admin/(?P<app_name>[^/]+)/(?P<model_name>[^/]+)-masschange/(?P<object_ids>[\w,\.\-:]+)/$',
        mass_change_view,
        name='massadmin_change_view'),
    url(r'^admin/', admin.site.urls),
    url(r'^accounts/', include('allauth.urls')),
    url(r'^$', RedirectToAPIRootView.as_view()),
]
