from rest_framework.response import Response
from models import *
from rest_framework import viewsets
from serializers.serializers import *

class EventViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Event.objects.all()
    serializer_class = EventSerializer

    def list(self, request, *args, **kwargs):
        args = {} if 'show_all' in request.QUERY_PARAMS else {'event_status': Event.SCHEDULED}

        if 'from' in request.QUERY_PARAMS:
            args['start_date__gte'] = request.QUERY_PARAM['from']

        if 'to' in request.QUERY_PARAMS:
            args['end_date__lte'] = request.QUERY_PARAM['to']

        events = Event.objects.filter(**args)
        obj = self.serializer_class(events, many=True)
        data = obj.data
        return Response(data)


class PlaceViewSet(viewsets.ModelViewSet):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer


class LanguageViewSet(viewsets.ModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
