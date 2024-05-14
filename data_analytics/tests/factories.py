import factory

from data_analytics.models import DataAnalyticsAuthToken
from helevents.tests.factories import UserFactory


class DataAnalyticsAuthTokenFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: "Test Token {0}".format(n))
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = DataAnalyticsAuthToken
