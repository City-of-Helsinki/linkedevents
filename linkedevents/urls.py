from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import path, re_path, reverse
from django.views.decorators.http import require_GET
from django.views.generic import RedirectView

from linkedevents import __version__

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


#
# Kubernetes liveness & readiness probes
#
@require_GET
def healthz(*args, **kwargs):
    return HttpResponse(status=200)


@require_GET
def readiness(*args, **kwargs):
    response_json = {
        "status": "ok",
        "packageVersion": __version__,
        "commitHash": settings.COMMIT_HASH,
        "buildTime": settings.APP_BUILD_TIME.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    return JsonResponse(response_json, status=200)


urlpatterns += [path("healthz", healthz), path("readiness", readiness)]
