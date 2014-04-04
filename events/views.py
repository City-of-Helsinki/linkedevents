import django_filters
from rest_framework.response import Response
from .models import Event, Place, Category, Organization, Language, Person
from rest_framework import viewsets
from .serializers import EventSerializer, CustomPaginationSerializer, \
    PlaceSerializer, CategorySerializer, OrganizationSerializer, \
    LanguageSerializer, PersonSerializer


class EventViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    pagination_serializer_class = CustomPaginationSerializer

    def list(self, request, *args, **kwargs):
        """
        TODO: convert to use proper filter framework
        """
        args = {} if 'show_all' in request.QUERY_PARAMS else {
            'event_status': Event.SCHEDULED}

        if 'from' in request.QUERY_PARAMS:
            args['start_date__gte'] = request.QUERY_PARAMS['from']

        if 'to' in request.QUERY_PARAMS:
            args['end_date__lte'] = request.QUERY_PARAMS['to']

        self.queryset = Event.objects.filter(**args)

        return super(EventViewSet, self).list(request, *args, **kwargs)


class PlaceViewSet(viewsets.ModelViewSet):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer
    pagination_serializer_class = CustomPaginationSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    pagination_serializer_class = CustomPaginationSerializer


class LanguageViewSet(viewsets.ModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    pagination_serializer_class = CustomPaginationSerializer
