def organization_post_save(sender, instance, created, **kwargs):
    if not created and instance.replaced_by:
        new_org = instance.replaced_by

        # copy old organization admin_users / regular_users to new organization
        new_org.admin_users.add(*list(instance.admin_users.all()))
        new_org.regular_users.add(*list(instance.regular_users.all()))

        # update owned systems to new owner
        instance.owned_systems.update(owner=new_org)
