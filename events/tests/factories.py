import factory

from events import utils
from events.auth import ApiKeyUser
from events.models import (
    DataSource,
    Event,
    Image,
    Keyword,
    KeywordLabel,
    Language,
    Offer,
    Place,
    Video,
)
from helevents.tests.factories import UserFactory


class DataSourceFactory(factory.django.DjangoModelFactory):
    id = factory.Sequence(lambda n: "data-source-{0}".format(n))

    class Meta:
        model = DataSource


class ApiKeyUserFactory(UserFactory):
    data_source = factory.SubFactory(DataSourceFactory)

    class Meta:
        model = ApiKeyUser


class OrganizationFactory(factory.django.DjangoModelFactory):
    data_source = factory.SubFactory(DataSourceFactory)

    class Meta:
        model = "django_orghierarchy.Organization"


class EventFactory(factory.django.DjangoModelFactory):
    data_source = factory.SubFactory(DataSourceFactory)
    publisher = factory.SubFactory(OrganizationFactory)

    class Meta:
        model = Event

    @factory.lazy_attribute_sequence
    def id(self, n):
        return f"{self.data_source.id}:{n}"


class DefaultOrganizationEventFactory(EventFactory):
    publisher = factory.LazyFunction(utils.get_or_create_default_organization)

    @factory.lazy_attribute_sequence
    def id(self, n):
        return f"{self.data_source.id}:{n}"

    @factory.lazy_attribute
    def data_source(self):
        return self.publisher.data_source


class KeywordLabelFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("bs")

    class Meta:
        model = KeywordLabel


class KeywordFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("bs")

    data_source = factory.SubFactory(DataSourceFactory)
    publisher = factory.SubFactory(OrganizationFactory)

    class Meta:
        model = Keyword

    @factory.lazy_attribute_sequence
    def id(self, n):
        return f"{self.data_source.id}:{n}"


class LanguageFactory(factory.django.DjangoModelFactory):
    id = "fi"
    name = "Finnish"

    class Meta:
        model = Language


class PlaceFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("bs")
    publisher = factory.SubFactory(OrganizationFactory)
    data_source = factory.SubFactory(DataSourceFactory)

    class Meta:
        model = Place

    @factory.lazy_attribute_sequence
    def id(self, n):
        return f"{self.data_source.id}:{n}"


class ImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Image


class OfferFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Offer


class VideoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Video
