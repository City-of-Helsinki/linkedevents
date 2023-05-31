import factory

from events import utils
from registrations.tests.factories import EventFactory


class DefaultOrganizationEventFactory(EventFactory):
    publisher = factory.LazyFunction(utils.get_or_create_default_organization)

    @factory.lazy_attribute_sequence
    def id(self, n):
        return f"{self.data_source.id}:{n}"

    @factory.lazy_attribute
    def data_source(self):
        return self.publisher.data_source
