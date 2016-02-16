# -*- coding: utf-8 -*-
from rest_framework.reverse import reverse
from rest_framework.routers import DefaultRouter
from rest_framework.response import Response
from rest_framework import views

class DocumentedRouter(DefaultRouter):
    # The following method overrides the DefaultRouter method with the
    # only difference being the view class name and docstring, which
    # are shown on the API front page.
    def get_api_root_view(self):
        """
        Return a view to use as the API root.
        """
        api_root_dict = {}
        list_name = self.routes[0].name
        for prefix, viewset, basename in self.registry:
            api_root_dict[prefix] = list_name.format(basename=basename)

        class LinkedEvents(views.APIView):
            """Linked Events provides categorized data on events and places.
            In the API, you can search data by date or location as
            well as city neighborhoods.

            The API provides data in JSON-LD format.

            *The API is in beta phase. To help improve the API, please don’t
            hesitate to comment, give feedback or make suggestions to
            [API's Github issues](https://github.com/City-of-Helsinki/linkedevents/issues) or
            through project page at [dev.hel.fi](http://dev.hel.fi/projects/linked-events/)*

            # Usage instructions

            Use the browsable version of the API at the bottom of this
            page to explore the data in your browser.

            Events are the main focus point of this API. Click on the event
            link below to see the documentation for events.

            # Browsable API

            """
            _ignore_model_permissions = True

            def get(self, request, format=None, version=None):
                ret = {}
                for key, url_name in api_root_dict.items():
                    ret[key] = reverse(url_name, request=request, format=format)
                return Response(ret)

        return LinkedEvents.as_view()
