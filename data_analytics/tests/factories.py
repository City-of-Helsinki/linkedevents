import factory

from data_analytics.models import DataAnalyticsApiToken
from helevents.tests.factories import UserFactory


class DataAnalyticsApiTokenFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: "Test Token {0}".format(n))
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = DataAnalyticsApiToken
