from django.test import TestCase
from django_orghierarchy.models import Organization

from events.models import DataSource
from ..models import User


class TestUser(TestCase):

    def setUp(self):
        self.user = User.objects.create(username='testuser')
        data_source = DataSource.objects.create(id='ds', name='data-source')

        self.org_1 = Organization.objects.create(data_source=data_source, origin_id='org-1')
        self.org_2 = Organization.objects.create(data_source=data_source, origin_id='org-2', replaced_by=self.org_1)

    def test_get_default_organization(self):
        self.org_1.admin_users.add(self.user)
        org = self.user.get_default_organization()
        self.assertEqual(org, self.org_1)

    def test_get_default_organization_org_replaced(self):
        self.org_2.admin_users.add(self.user)
        org = self.user.get_default_organization()
        self.assertIsNone(org)
