from django_orghierarchy.models import Organization
from helusers.models import AbstractUser

from events.permissions import UserModelPermissionMixin


class User(AbstractUser, UserModelPermissionMixin):
    def __str__(self):
        return ' - '.join([self.get_display_name(), self.email])

    def get_display_name(self):
        return '{0} {1}'.format(self.first_name, self.last_name).strip()

    def get_default_organization(self):
        admin_org = self.admin_organizations.filter(
            replaced_by__isnull=True,
        ).order_by('created_time').first()

        regular_org = self.organization_memberships.filter(
            replaced_by__isnull=True,
        ).order_by('created_time').first()

        return admin_org or regular_org

    def is_admin(self, publisher):
        # check if publisher exists in user's admin organizations and their descedants
        admin_orgs = self.admin_organizations.all()
        for org in admin_orgs:
            if org.get_descendants(include_self=True).filter(id=publisher.id).exists():
                return True

        # check if publisher exists in affiliated organizations of user's admin organizations
        if Organization.objects.filter(responsible_organization__in=admin_orgs, id=publisher.id).exists():
            return True

        return False

    def is_regular_user(self, publisher):
        return self.organization_memberships.filter(id=publisher.id).exists()
