# django
from django.utils import timezone

# 3rd party
from rest_framework.reverse import reverse

# this app
from events.api import KeywordSerializer, PlaceSerializer
from events.models import DataSource, Organization


class TestDataMixin:

    def set_up_test_data(self):

        # dummy inputs
        TEXT = 'testing'

        # data source
        self.test_ds, _ = DataSource.objects.get_or_create(id=TEXT)

        #  organization
        self.test_org, _ = Organization.objects.get_or_create(
            id=TEXT,
            data_source=self.test_ds
        )
