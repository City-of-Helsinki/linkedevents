# Generated by Django 2.2.9 on 2020-01-21 08:09

from django.db import migrations

NOTIFICATION_TYPES = ("unpublished_event_deleted", "event_published", "draft_posted")
LANGUAGES = ["fi", "sv", "en"]
DEFAULT_LANGUAGE = "fi"

FOOTER_FI = "Tämä on automaattinen viesti Helsingin kaupungin tapahtumarajapinnasta. Viestiin ei voi vastata.\n"
FOOTER_SV = "Detta är ett automatiskt meddelande från Helsingfors stads evenemangsgränssnitt. Det är inte möjligt att svara på det här meddelandet.\n"
FOOTER_EN = "This is an automatic message from the City of Helsinki’s Event API. This is a no-reply message.\n"

HTML_SEPARATOR = "\n<br/><br/>\n"

UNPUBLISHED_EVENT_DELETED_SUBJECT_FI = (
    'Tapahtumailmoituksesi "{{ event.name }}" on poistettu – Helsingin kaupunki'
)
UNPUBLISHED_EVENT_DELETED_HTML_BODY_FI = """Helsingin kaupungille {{ event.created_time|format_datetime('fi') }} ilmoittamasi tapahtuma "{{ event.name }}" on poistettu.
<br/><br/>
Ilmoituksesi poistettiin, joko 1) koska se ei noudattanut Helsingin kaupungin <a href="https://linkedevents.hel.fi/terms">tapahtumarajapinnan käyttöehtoja</a> tai 2) koska tapahtuman ei muusta syystä katsottu sopivan kaupungin tapahtumarajapintaan.
<br/><br/>
Jos haluat lisätietoja, voit jättää asiasta kysymyksen osoitteessa <a href="https://hel.fi/palaute">hel.fi/palaute.</a> Mainitse palautteessasi tapahtuman nimi ja julkaisuaika: "{{ event.name }}", {{ event.created_time|format_datetime('fi') }}"""

UNPUBLISHED_EVENT_DELETED_SUBJECT_SV = (
    'Din evenemangsanmälan "{{ event.name }}" har strukits – Helsingfors stad'
)
UNPUBLISHED_EVENT_DELETED_HTML_BODY_SV = """Evenemanget "{{ event.name }}" som du har anmält till Helsingfors stad {{ event.created_time|format_datetime('sv') }} har strukits.
<br/><br/>
Din anmälan ströks antingen 1) eftersom det inte <a href="https://linkedevents.hel.fi/terms">uppfyllde användarvillkoren för Helsingfors stads evenemangsgränssnitt</a> eller 2) eftersom det av annan orsak inte ansågs lämpa sig för stadens evenemangsgränssnitt.
<br/><br/>
Om du vill ha ytterligare upplysningar, kan du lämna en fråga om saken på <a href="https://hel.fi/respons">hel.fi/respons</a>. I din respons, nämn evenemangets namn och publiceringstid:
<br/><br/>
"{{ event.name }}", {{ event.created_time|format_datetime('sv') }}"""

UNPUBLISHED_EVENT_DELETED_SUBJECT_EN = (
    'Your event registration "{{ event.name }}" has been removed – City of Helsinki'
)
UNPUBLISHED_EVENT_DELETED_HTML_BODY_EN = """The "{{ event.name }}" event that you registered to the City of Helsinki on {{ event.created_time|format_datetime('en') }} has been removed.
<br/><br/>
You registration was removed either 1) because it did not adhere to <a href="https://linkedevents.hel.fi/terms">the terms and conditions of the City of Helsinki’s Event API</a> or 2) because the event was not deemed suitable for the City's Event API for another reason.
<br/><br/>
If you want further information, you can submit a question about it on <a href="https://hel.fi/feedback">hel.fi/feedback</a>. In your feedback, please mention the event’s name and time of publication:
<br/><br/>
"{{ event.name }}", {{ event.created_time|format_datetime('en') }}"""

EVENT_PUBLISHED_SUBJECT_FI = (
    'Tapahtumailmoituksesi "{{ event.name }}" on julkaistu – Helsingin kaupunki'
)
EVENT_PUBLISHED_HTML_BODY_FI = """Helsingin kaupungille {{ event.created_time|format_datetime('fi') }} ilmoittamasi tapahtuma "{{ event.name }}" on julkaistu.
<br/><br/>
Tapahtuma tulee näkyville <a href="https://hel.fi/tapahtumat">Helsingin tapahtumakalenteriin</a> enintään tunnin viiveellä. Tapahtuma voidaan näyttää myös muissa kalentereissa, jotka hakevat tietoja Helsingin kaupungin tapahtumarajapinnasta.
<br/><br/>
Et voi enää muokata tapahtumaa julkaisun jälkeen. Jos haluat muuttaa tapahtuman tietoja, jätä muutospyyntö osoitteessa <a href="https://hel.fi/palaute">hel.fi/palaute</a>. Mainitse palautteessasi tapahtuman nimi ja julkaisuaika:"{{ event.name }}", {{ event.created_time|format_datetime('fi') }}"""

EVENT_PUBLISHED_SUBJECT_SV = (
    'Din evenemangsanmälan "{{ event.name }}" har publicerats – Helsingfors stad'
)
EVENT_PUBLISHED_HTML_BODY_SV = """Evenemanget ”{{ event.name }}” som du har anmält till Helsingfors stad {{ event.created_time|format_datetime('sv') }} har publicerats.
<br/><br/>
Evenemanget publiceras i <a href="https://hel.fi/tapahtumat">Helsingfors evenemangskalender</a> med högst en timmes fördröjning. Evenemanget kan visas också i andra kalendrar som söker data ur Helsingfors stads evenemangsgränssnitt.
<br/><br/>
Du kan inte längre redigera evenemanget efter att det har publicerats. Om du vill ändra på uppgifterna för evenemanget, lämna en begäran om ändring på adressen hel.fi/respons. I din respons, nämn evenemangets namn och publiceringstid:
<br/><br/>
"{{ event.name }}", {{ event.created_time|format_datetime('sv') }}"""

EVENT_PUBLISHED_SUBJECT_EN = (
    'Your event registration "{{ event.name }}" has been published – City of Helsinki'
)
EVENT_PUBLISHED_HTML_BODY_EN = """The "{{ event.name }}" event that you registered to the City of Helsinki on {{ event.created_time|format_datetime('en') }} has been published.
<br/><br/>
The event will become visible <a href="https://hel.fi/tapahtumat">in Helsinki’s event calendar</a> within an hour at most. The event can also be shown in other calendars, which look up data from the City of Helsinki’s Event API.
<br/><br/>
You can no longer edit the event when it has been published. If you want to change the event data, submit a change request on hel.fi/feedback. In your feedback, please mention the event’s name and time of publication:
<br/><br/>
"{{ event.name }}", {{ event.created_time|format_datetime('en') }}"""

DRAFT_POSTED_SUBJECT_FI = "Uusi tapahtumaluonnos \"{{ event.name }}\", {{ event.created_time|format_datetime('fi') }} – Helsingin kaupungin tapahtumarajapinta"
DRAFT_POSTED_HTML_BODY_FI = """Helsingin kaupungin tapahtumarajapintaan on luotu uusi tapahtumaluonnos:
<br/><br/>
"{{ event.name }}", {{ event.created_time|format_datetime('fi') }}
<br/><br/>
<a href="https://linkedevents.hel.fi/event/{{ event.id }}">Siirry moderoimaan tapahtumia »</a>
<br/><br/>
Sait tämän viestin, koska olet moderaattori organisaatiossa {{ event.publisher.name }}."""

DRAFT_POSTED_SUBJECT_SV = "Nytt evenemangsutkast \"{{ event.name }}\", {{ event.created_time|format_datetime('sv') }} – Helsingfors stads evenemangsgränssnitt"
DRAFT_POSTED_HTML_BODY_SV = """Ett nytt evenemangsutkast har skapats i Helsingfors stads evenemangsgränssnitt.
<br/><br/>
"{{ event.name }}", {{ event.created_time|format_datetime('sv') }}
<br/><br/>
<a href="https://linkedevents.hel.fi/event/{{ event.id }}">Siirry moderoimaan tapahtumia »</a>
<br/><br/>
Du fick det här meddelandet eftersom du är moderator i organisationen {{ event.publisher.name }}."""

DRAFT_POSTED_SUBJECT_EN = "New event draft \"{{ event.name }}\", {{ event.created_time|format_datetime('en') }} – City of Helsinki Event API"
DRAFT_POSTED_HTML_BODY_EN = """A new event draft has been created in the City of Helsinki’s Event API:
<br/><br/>
"{{ event.name }}", {{ event.created_time|format_datetime('en') }}
<br/><br/>
<a href="https://linkedevents.hel.fi/event/{{ event.id }}">Go to moderate events »</a>
<br/><br/>
You received this message because you are a moderator in the {{ event.publisher.name }} organisation."""


def _append_footer(text, language, separator):
    var_name = "FOOTER_{}".format(language).upper()
    footer = globals().get(var_name)
    assert footer, "{} undefined".format(var_name)
    return separator.join([text, footer])


def _get_text(notification_type, language, field):
    var_name = "{}_{}_{}".format(notification_type, field, language).upper()
    text = globals().get(var_name)
    assert text, "{} undefined".format(var_name)
    return text


def create_existing_notifications(NotificationTemplate):
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
                setattr(notification, "subject_{}".format(language), subject)
                setattr(notification, "html_body_{}".format(language), html_body)
            notification.save()


def forwards(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    create_existing_notifications(NotificationTemplate)


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
