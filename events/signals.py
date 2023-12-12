import logging

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver

from notifications.models import (
    NotificationTemplateException,
    NotificationType,
    render_notification_template,
)
from registrations.utils import get_email_noreply_address

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


# TODO not in use anymore, remove altogether?
def user_created_notification(sender, instance, created, **kwargs):
    """Send a notification to superusers when a user gets created."""
    if created:
        user_model = get_user_model()
        recipient_list = [
            item
            for item in user_model.objects.filter(is_superuser=True)
            .exclude(email__exact="")
            .values_list("email", flat=True)
        ]
        notification_type = NotificationType.USER_CREATED
        context = {"user": instance}

        if len(recipient_list) == 0:
            logger.warning(
                "No recipients for notification type '%s'" % notification_type,
                extra={"user": instance.username},
            )
            return

        try:
            rendered_notification = render_notification_template(
                notification_type, context
            )
        except NotificationTemplateException as e:
            logger.error(e, exc_info=True)
            return

        send_mail(
            rendered_notification["subject"],
            rendered_notification["body"],
            get_email_noreply_address(),
            recipient_list,
            html_message=rendered_notification["html_body"],
        )
