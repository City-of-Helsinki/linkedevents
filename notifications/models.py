import logging

from django.conf import settings
from django.db import models
from django.utils import translation, timezone
from django.utils.html import strip_tags
from django.utils.translation import activate
from django.utils.translation import ugettext_lazy as _
from django.utils.formats import date_format
from jinja2 import StrictUndefined
from jinja2.exceptions import TemplateError
from jinja2.sandbox import SandboxedEnvironment

DEFAULT_LANG = settings.LANGUAGES[0][0]

logger = logging.getLogger(__name__)


class NotificationType:
    UNPUBLISHED_EVENT_DELETED = 'unpublished_event_deleted'
    EVENT_PUBLISHED = 'event_published'
    DRAFT_POSTED = 'draft_posted'
    USER_CREATED = 'user_created'


class NotificationTemplateException(Exception):
    pass


class NotificationTemplate(models.Model):
    NOTIFICATION_TYPE_CHOICES = (
        (NotificationType.UNPUBLISHED_EVENT_DELETED, _('Unpublished event deleted')),
        (NotificationType.EVENT_PUBLISHED, _('Event published')),
        (NotificationType.DRAFT_POSTED, _('Draft posted')),
        (NotificationType.USER_CREATED, _('User created')),
    )

    type = models.CharField(
        verbose_name=_('Type'), choices=NOTIFICATION_TYPE_CHOICES, max_length=100, unique=True, db_index=True
    )

    subject = models.CharField(verbose_name=_('Subject'), max_length=200, help_text=('Subject for email notifications'))

    body = models.TextField(verbose_name=_('Body'), help_text=_('Text body for email notifications'), blank=True)

    html_body = models.TextField(verbose_name=_('HTML Body'), help_text=_('HTML body for email notifications'), blank=True)

    class Meta:
        verbose_name = _('Notification template')
        verbose_name_plural = _('Notification templates')

    def __str__(self):
        for t in self.NOTIFICATION_TYPE_CHOICES:
            if t[0] == self.type:
                return str(t[1])
        return 'N/A'

    def render(self, context, language_code=DEFAULT_LANG):
        """
        Render this notification template with given context and language

        Returns a dict containing all content fields of the template. Example:

        {'subject': 'bar', 'body': 'baz', 'html_body': '<b>foobar</b>'}

        """

        env = SandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
        env.filters['format_datetime'] = format_datetime

        logger.debug('Rendering template for notification %s' % self.type)

        activate(language_code)

        try:
            rendered_notification = {
                attr: env.from_string(getattr(self, attr)).render(context)
                for attr in ('subject', 'html_body')
            }
            if self.body:
                rendered_notification['body'] = env.from_string(self.body).render(context)
            else:
                # if text body is empty use html body without tags as text body
                rendered_notification['body'] = strip_tags(rendered_notification['html_body'])
            return rendered_notification
        except TemplateError as e:
            raise NotificationTemplateException(e) from e


def format_datetime(dt, lang='fi'):
    dt = timezone.template_localtime(dt)
    if lang == 'fi':
        # 1.1.2017 klo 12:00
        dt_format = r'j.n.Y \k\l\o G:i'
    elif lang == 'sv':
        # 1.1.2017 kl. 12:00
        dt_format = r'j.n.Y \k\l\. G:i'
    elif lang == 'en':
        # 1 Jan 2017 at 12:00
        dt_format = r'j M Y \a\t G:i'
    else:
        raise NotificationTemplateException(f"format_datetime received unknown language '{lang}'")

    return date_format(dt, dt_format)


def render_notification_template(notification_type, context, language_code=DEFAULT_LANG):
    try:
        template = NotificationTemplate.objects.get(type=notification_type)
    except NotificationTemplate.DoesNotExist as e:
        raise NotificationTemplateException(e) from e

    return template.render(context, language_code)
