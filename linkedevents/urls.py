from django.urls import path, re_path, reverse, include
from django.views.generic import RedirectView

from .api import LinkedEventsAPIRouter
from helusers.admin_site import admin

api_router = LinkedEventsAPIRouter()


class RedirectToAPIRootView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse('api-root', kwargs={'version': 'v1'})


urlpatterns = [
    re_path(r'^(?P<version>(v0.1|v1))/', include(api_router.urls)),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^accounts/', include('allauth.urls')),
    re_path(r'^$', RedirectToAPIRootView.as_view()),
    path('', include('social_django.urls', namespace='social')),
    path('', include('helusers.urls', 'helusers'))
]
