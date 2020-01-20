from django.views.generic import View
from django.http import HttpResponse


class HealthResponse(View):
    @staticmethod
    def get(*args, **kwargs):
        return HttpResponse(status=200, content="OK")
