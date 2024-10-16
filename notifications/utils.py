from django.conf import settings
from django.utils import timezone
from django.utils.formats import date_format

from notifications.exceptions import NotificationTemplateError

DEFAULT_LANG = settings.LANGUAGES[0][0]


def format_datetime(dt, lang="fi"):
    dt = timezone.template_localtime(dt)
    if lang == "fi":
        # 1.1.2017 klo 12:00
        dt_format = r"j.n.Y \k\l\o G:i"
    elif lang == "sv":
        # 1.1.2017 kl. 12:00
        dt_format = r"j.n.Y \k\l\. G:i"
    elif lang == "en":
        # 1 Jan 2017 at 12:00
        dt_format = r"j M Y \a\t G:i"
    else:
        raise NotificationTemplateError(
            f"format_datetime received unknown language '{lang}'"
        )

    return date_format(dt, dt_format)


def format_date(dt, lang="fi"):
    dt = timezone.template_localtime(dt)

    if lang in ("fi", "sv"):
        # 1.1.2017
        dt_format = r"j.n.Y"
    elif lang == "en":
        # 1 Jan 2017
        dt_format = r"j M Y"
    else:
        raise NotificationTemplateError(
            f"format_date received unknown language '{lang}'"
        )

    return date_format(dt, dt_format)
