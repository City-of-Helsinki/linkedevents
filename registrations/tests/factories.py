import factory

from events.tests.factories import EventFactory
from registrations.models import Registration, SeatReservationCode, SignUp, SignUpGroup


class RegistrationFactory(factory.django.DjangoModelFactory):
    event = factory.SubFactory(EventFactory)

    class Meta:
        model = Registration


class SignUpGroupFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)

    class Meta:
        model = SignUpGroup


class SignUpFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)

    class Meta:
        model = SignUp


class SeatReservationCodeFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)

    class Meta:
        model = SeatReservationCode
