import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(
    post_save,
    sender="django_orghierarchy.Organization",
    dispatch_uid="organization_replaced",
)
def organization_replaced(sender, instance, created, **kwargs):
    """Copy users from the old organization to the new one."""
    if not created and instance.replaced_by:
        new_org = instance.replaced_by

        # copy old organization admin_users / regular_users to new organization
        new_org.admin_users.add(*list(instance.admin_users.all()))
        new_org.regular_users.add(*list(instance.regular_users.all()))

        # update owned systems to new owner
        instance.owned_systems.update(owner=new_org)
