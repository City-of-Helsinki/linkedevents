from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.urls import path, re_path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

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
        RedirectView.as_view(pattern_name="schema-unversioned", permanent=True),
        name="legacy-schema",
    ),
    path(
        "docs/swagger-ui/",
        RedirectView.as_view(pattern_name="swagger-ui-unversioned", permanent=True),
        name="legacy-swagger-ui",
    ),
    # Kubernetes liveness & readiness probes
    path("", include("helsinki_health_endpoints.urls")),
    # Redirect root to versioned API documentation
    path("", RedirectView.as_view(url="/v1/", permanent=False)),
    # API router must come after specific doc paths to avoid conflicts
    re_path(r"^(?P<version>(v0.1|v1))/", include(api_router.urls)),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
