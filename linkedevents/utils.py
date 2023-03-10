from django.conf import settings
from rest_framework.routers import APIRootView
from rest_framework.views import get_view_name as original_get_view_name


def get_view_name(view):
    if type(view) is APIRootView:
        return getattr(settings, "INSTANCE_NAME", "Linked Events")
    return original_get_view_name(view)
