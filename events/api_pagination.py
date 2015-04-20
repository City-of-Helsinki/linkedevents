from rest_framework.response import Response
from rest_framework.compat import OrderedDict
from rest_framework import pagination


# This needs to be in its own file because of circular
# imports.
class CustomPagination(pagination.PageNumberPagination):
    def get_paginated_response(self, data):
        meta = OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
        ])

        return Response(OrderedDict([('meta', meta), ('data', data)]))
