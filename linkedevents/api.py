import copy

from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

from linkedevents.registry import all_views


class LinkedEventsAPIRouter(DefaultRouter):
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

        if settings.ENABLE_REGISTRATION_ENDPOINTS:
            import registrations.api  # noqa

        for view in all_views:
            self._register_view(view)
