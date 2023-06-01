import factory

from events import utils
from events.models import DataSource, Event


class DataSourceFactory(factory.django.DjangoModelFactory):
    id = factory.Sequence(lambda n: "data-source-{0}".format(n))

    class Meta:
        model = DataSource


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
