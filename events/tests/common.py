from django_orghierarchy.models import Organization

# this app
from events.models import DataSource


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
