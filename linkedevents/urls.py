from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import path, re_path
from django.views.decorators.http import require_GET
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from linkedevents import __version__

from .api import CustomSpectacularSwaggerView, LinkedEventsAPIRouter

api_router = LinkedEventsAPIRouter()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("pysocial/", include("social_django.urls", namespace="social")),
    path("helauth/", include("helusers.urls")),
    path("gdpr-api/", include("helsinki_gdpr.urls")),
    path("data-analytics/", include("data_analytics.urls", namespace="data_analytics")),
    # Alternative non-versioned paths (also point to current docs)
    path(
        "api-docs/schema/",
        SpectacularAPIView.as_view(api_version="v1"),
        name="schema-unversioned",
    ),
    path(
        "api-docs/swagger-ui/",
        CustomSpectacularSwaggerView.as_view(url_name="schema-unversioned"),
        name="swagger-ui-unversioned",
    ),
    path(
        "api-docs/",
        SpectacularRedocView.as_view(url_name="schema-unversioned"),
        name="redoc-unversioned",
    ),
    # Legacy redirects for backward compatibility
    path(
        "docs/schema/",
        RedirectView.as_view(url="/api-docs/schema/", permanent=True),
        name="legacy-schema",
    ),
    path(
        "docs/swagger-ui/",
        RedirectView.as_view(url="/api-docs/swagger-ui/", permanent=True),
        name="legacy-swagger-ui",
    ),
    # Redirect root to versioned API documentation
    path("", RedirectView.as_view(url="/v1/", permanent=False)),
    # API router must come after specific doc paths to avoid conflicts
    re_path(r"^(?P<version>(v0.1|v1))/", include(api_router.urls)),
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
