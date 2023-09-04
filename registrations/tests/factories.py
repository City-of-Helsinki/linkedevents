import factory

from events.tests.factories import EventFactory
from registrations.models import (
    Registration,
    RegistrationUserAccess,
    SignUp,
    SignUpGroup,
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
