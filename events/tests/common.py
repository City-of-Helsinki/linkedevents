from django_orghierarchy.models import Organization

# this app
from events.models import DataSource


class TestDataMixin:
    def set_up_test_data(self):

        # dummy inputs
        text = "testing"

        # data source
        self.test_ds, _ = DataSource.objects.get_or_create(id=text)

        #  organization
        self.test_org, _ = Organization.objects.get_or_create(
            id=text, data_source=self.test_ds
        )
