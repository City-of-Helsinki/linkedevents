from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.urls import path, re_path, reverse
from django.views.generic import RedirectView

from .api import LinkedEventsAPIRouter

api_router = LinkedEventsAPIRouter()


class RedirectToAPIRootView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse("api-root", kwargs={"version": "v1"})


urlpatterns = [
    re_path(r"^(?P<version>(v0.1|v1))/", include(api_router.urls)),
    path("admin/", admin.site.urls),
    path("pysocial/", include("social_django.urls", namespace="social")),
    path("helauth/", include("helusers.urls")),
    path("gdpr-api/", include("helsinki_gdpr.urls")),
    path("", RedirectToAPIRootView.as_view()),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
