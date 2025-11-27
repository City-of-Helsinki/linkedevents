from django.db import migrations

NOTIFICATION_TYPES = ("user_created",)
LANGUAGES = ["fi"]
DEFAULT_LANGUAGE = "fi"

FOOTER_FI = "Tämä on automaattinen viesti Helsingin kaupungin tapahtumarajapinnasta. Viestiin ei voi vastata.\n"

HTML_SEPARATOR = "\n<br/><br/>\n"

USER_CREATED_SUBJECT_FI = (
    "Uusi käyttäjätunnus luotu - {{ user.date_joined|format_datetime('fi') }}"
)
USER_CREATED_HTML_BODY_FI = """Tapahtumarajapintaan on luotu uusi käyttäjätunnus {{ user.date_joined|format_datetime('fi') }}:
<br/><br/>
<a href="mailto:{{ user.email }}">{{ user.email }}</a>
<br/><br/>
<a href="https://api.hel.fi/linkedevents/admin/django_orghierarchy/organization/">Siirry käyttäjien hallintaan »</a>"""


def _append_footer(text, language, separator):
    var_name = f"FOOTER_{language}".upper()
    footer = globals().get(var_name)
    assert footer, f"{var_name} undefined"
    return separator.join([text, footer])


def _get_text(notification_type, language, field):
    var_name = f"{notification_type}_{field}_{language}".upper()
    text = globals().get(var_name)
    assert text, f"{var_name} undefined"
    return text


def create_existing_notifications(NotificationTemplate):  # noqa: N803
    for notification_type in NOTIFICATION_TYPES:
        subject = _get_text(notification_type, DEFAULT_LANGUAGE, "subject")
        html_body = _get_text(notification_type, DEFAULT_LANGUAGE, "html_body")
        html_body = _append_footer(html_body, DEFAULT_LANGUAGE, HTML_SEPARATOR)
        try:
            notification = NotificationTemplate.objects.get(type=notification_type)
            continue
        except NotificationTemplate.DoesNotExist:
            pass
        notification, created = NotificationTemplate.objects.get_or_create(
            type=notification_type, subject=subject, html_body=html_body
        )
        if created:
            for language in LANGUAGES:
                subject = _get_text(notification_type, language, "subject")
                html_body = _get_text(notification_type, language, "html_body")
                html_body = _append_footer(html_body, language, HTML_SEPARATOR)
                setattr(notification, f"subject_{language}", subject)
                setattr(notification, f"html_body_{language}", html_body)
            notification.save()


def forwards(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    create_existing_notifications(NotificationTemplate)


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_create_default_templates"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
