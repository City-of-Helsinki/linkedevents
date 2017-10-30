from rest_framework.response import Response
from collections import OrderedDict
from rest_framework import pagination


# This needs to be in its own file because of circular
# imports.
class CustomPagination(pagination.PageNumberPagination):
    max_page_size = 100
    page_size_query_param = 'page_size'

    def get_paginated_response(self, data):
        meta = OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
        ])

        return Response(OrderedDict([('meta', meta), ('data', data)]))


class LargeResultsSetPagination(CustomPagination):
    page_size = 1000
    page_size_query_param = 'page_size'
    max_page_size = 10000
