import factory

from events.tests.factories import EventFactory
from registrations.models import Registration


class RegistrationFactory(factory.django.DjangoModelFactory):
    event = factory.SubFactory(EventFactory)

    class Meta:
        model = Registration
