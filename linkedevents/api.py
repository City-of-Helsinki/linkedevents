import copy
from rest_framework.routers import DefaultRouter, SimpleRouter
from events.api import all_views as events_views
from helevents.api import all_views as users_views


class LinkedEventsAPIRouter(DefaultRouter):
    # these are from Django REST Framework bulk BulkRouter with 'delete' excluded
    routes = copy.deepcopy(SimpleRouter.routes)
    routes[0].mapping.update({
        'put': 'bulk_update',
        'patch': 'partial_bulk_update',
    })

    def __init__(self):
        super(LinkedEventsAPIRouter, self).__init__()
        self.registered_api_views = set()
        self._register_all_views()

    def _register_view(self, view):
        if view['class'] in self.registered_api_views:
            return
        self.registered_api_views.add(view['class'])
        self.register(view['name'], view['class'], basename=view.get("basename"))

    def _register_all_views(self):
        for view in events_views:
            self._register_view(view)
        for view in users_views:
            self._register_view(view)
