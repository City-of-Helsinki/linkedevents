from django.test import TestCase
from django_orghierarchy.models import Organization

from events.models import DataSource
from ..auth import ApiKeyUser


class TestApiKeyUser(TestCase):

    def setUp(self):
        self.data_source = DataSource.objects.create(
            id='ds',
            name='data-source',
        )
        self.org_1 = Organization.objects.create(
            data_source=self.data_source,
            origin_id='org-1',
        )
        self.org_2 = Organization.objects.create(
            data_source=self.data_source,
            origin_id='org-2',
            replaced_by=self.org_1,
        )
        self.data_source.owner = self.org_1
        self.data_source.save()

        self.user = ApiKeyUser.objects.create(
            username='testuser',
            data_source=self.data_source,
        )

    def test_is_admin(self):
        is_admin = self.user.is_admin(self.org_1)
        self.assertTrue(is_admin)

        is_admin = self.user.is_admin(self.org_2)
        self.assertFalse(is_admin)

    def test_is_regular_user(self):
        is_regular_user = self.user.is_regular_user(self.org_1)
        self.assertFalse(is_regular_user)

        is_regular_user = self.user.is_regular_user(self.org_2)
        self.assertFalse(is_regular_user)
