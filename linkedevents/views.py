from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


@extend_schema(exclude=True)
class RemovedSearchView(APIView):
    def get(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "This endpoint has been removed. Use /event/?full_text=... "
                    "for event searches or /place/?text=... for place searches."
                )
            },
            status=status.HTTP_410_GONE,
        )
