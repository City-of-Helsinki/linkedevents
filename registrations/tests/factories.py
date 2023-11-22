import factory

from events.tests.factories import EventFactory
from registrations.models import (
    Registration,
    RegistrationUserAccess,
    SeatReservationCode,
    SignUp,
    SignUpContactPerson,
    SignUpGroup,
    SignUpGroupProtectedData,
    SignUpProtectedData,
)


class RegistrationFactory(factory.django.DjangoModelFactory):
    event = factory.SubFactory(EventFactory)

    class Meta:
        model = Registration


class RegistrationUserAccessFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)

    class Meta:
        model = RegistrationUserAccess


class SignUpGroupFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)

    class Meta:
        model = SignUpGroup


class SignUpFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)

    class Meta:
        model = SignUp


class SignUpContactPersonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SignUpContactPerson


class SignUpGroupProtectedDataFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)
    signup_group = factory.SubFactory(SignUpGroupFactory)

    class Meta:
        model = SignUpGroupProtectedData


class SignUpProtectedDataFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)
    signup = factory.SubFactory(SignUpFactory)

    class Meta:
        model = SignUpProtectedData


class SeatReservationCodeFactory(factory.django.DjangoModelFactory):
    registration = factory.SubFactory(RegistrationFactory)

    class Meta:
        model = SeatReservationCode
