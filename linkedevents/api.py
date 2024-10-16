import copy
from collections import OrderedDict

from django.urls import NoReverseMatch
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.routers import APIRootView, DefaultRouter, SimpleRouter

from linkedevents.registry import all_views


class CustomAPIRootView(APIRootView):
    name = "Linked Events"

    def get(self, request, *args, **kwargs):
        # Return a plain {"name": "hyperlink"} response.
        ret = OrderedDict()
        namespace = request.resolver_match.namespace
        for key, url_name in self.api_root_dict.items():
            # Don't show data source, feedback and organization class routes in the
            # api root
            if url_name in [
                "datasource-list",
                "organizationclass-list",
                "feedback-list",
                "guest-feedback-list",
            ]:
                continue

            if namespace:
                url_name = namespace + ":" + url_name
            try:
                ret[key] = reverse(
                    url_name,
                    args=args,
                    kwargs=kwargs,
                    request=request,
                    format=kwargs.get("format"),
                )
            except NoReverseMatch:
                # Don't bail out if eg. no list routes exist, only detail routes.
                continue

        return Response(ret)


class LinkedEventsAPIRouter(DefaultRouter):
    APIRootView = CustomAPIRootView
    # these are from Django REST Framework bulk BulkRouter with 'delete' excluded
    routes = copy.deepcopy(SimpleRouter.routes)
    routes[0].mapping.update(
        {
            "put": "bulk_update",
            "patch": "partial_bulk_update",
        }
    )

    def __init__(self):
        super().__init__()
        self.registered_api_views = set()
        self._register_all_views()

    def _register_view(self, view):
        if view["class"] in self.registered_api_views:
            return
        self.registered_api_views.add(view["class"])
        self.register(view["name"], view["class"], basename=view.get("base_name"))

    def _register_all_views(self):
        # Imports run register_view for all views
        import events.api  # noqa
        import helevents.api  # noqa
        import registrations.api  # noqa

        for view in all_views:
            self._register_view(view)


class CustomSpectacularSwaggerView(SpectacularSwaggerView):
    template_name = "swagger_ui.html"
