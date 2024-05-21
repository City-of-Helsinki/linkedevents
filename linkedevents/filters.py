from rest_framework import filters


class LinkedEventsOrderingFilter(filters.OrderingFilter):
    ordering_param = "sort"
