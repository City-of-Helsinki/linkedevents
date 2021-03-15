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

        private_org = self.public_memberships.filter(
            replaced_by__isnull=True,
        ).order_by('created_time').first()

        return admin_org or regular_org or private_org

    def is_admin(self, publisher):
        return publisher in self.get_admin_organizations_and_descendants()

    def is_regular_user(self, publisher):
        return self.organization_memberships.filter(id=publisher.id).exists()

    def is_private_user(self, publisher):
        return self.public_memberships.filter(id=publisher.id).exists()
