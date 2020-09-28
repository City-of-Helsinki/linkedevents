import pytest
from datetime import datetime
import pytz

from django.utils import timezone
from django.utils.translation import activate
from notifications.models import NotificationType, NotificationTemplate, render_notification_template


@pytest.fixture(scope='function')
def notification_type():
    setattr(NotificationType, 'TEST', 'test')
    yield NotificationType.TEST
    delattr(NotificationType, 'TEST')


@pytest.fixture
def notification_template(notification_type):
    template = NotificationTemplate.objects.create(
        type=NotificationType.TEST,
        subject_en="test subject, variable value: {{ subject_var }}!",
        body_en="test body, variable value: {{ body_var }}!",
        html_body_en="test <b>HTML</b> body, variable value: {{ html_body_var }}!",
    )
    activate('fi')
    template.subject = "testiotsikko, muuttujan arvo: {{ subject_var }}!"
    template.body = "testiruumis, muuttujan arvo: {{ body_var }}!"
    template.html_body = "testi<b>hötömölö</b>ruumis, muuttujan arvo: {{ html_body_var }}!"
    template.save()

    return template


@pytest.mark.django_db
def test_notification_template_rendering(notification_template):
    context = {
        'subject_var': 'bar',
        'body_var': 'baz',
        'html_body_var': 'foo <b>bar</b> baz',
    }

    rendered = render_notification_template(NotificationType.TEST, context, 'en')
    assert len(rendered) == 3
    assert rendered['subject'] == "test subject, variable value: bar!"
    assert rendered['body'] == "test body, variable value: baz!"
    assert rendered['html_body'] == "test <b>HTML</b> body, variable value: foo <b>bar</b> baz!"

    rendered = render_notification_template(NotificationType.TEST, context, 'fi')
    assert len(rendered) == 3
    assert rendered['subject'] == "testiotsikko, muuttujan arvo: bar!"
    assert rendered['body'] == "testiruumis, muuttujan arvo: baz!"
    assert rendered['html_body'] == "testi<b>hötömölö</b>ruumis, muuttujan arvo: foo <b>bar</b> baz!"


@pytest.mark.django_db
def test_notification_template_rendering_empty_text_body(notification_template):
    context = {
        'subject_var': 'bar',
        'body_var': 'baz',
        'html_body_var': 'foo <b>bar</b> baz',
    }

    activate('fi')
    notification_template.body = ''
    notification_template.save()

    rendered = render_notification_template(NotificationType.TEST, context, 'fi')
    assert len(rendered) == 3
    assert rendered['subject'] == "testiotsikko, muuttujan arvo: bar!"
    assert rendered['body'] == "testihötömölöruumis, muuttujan arvo: foo bar baz!"
    assert rendered['html_body'] == "testi<b>hötömölö</b>ruumis, muuttujan arvo: foo <b>bar</b> baz!"


@pytest.mark.django_db
def test_notification_template_rendering_empty_html_body(notification_template):
    context = {
        'subject_var': 'bar',
        'body_var': 'baz',
        'html_body_var': 'foo <b>bar</b> baz',
    }

    activate('fi')
    notification_template.html_body = ''
    notification_template.save()

    rendered = render_notification_template(NotificationType.TEST, context, 'fi')
    assert len(rendered) == 3
    assert rendered['subject'] == "testiotsikko, muuttujan arvo: bar!"
    assert rendered['body'] == "testiruumis, muuttujan arvo: baz!"
    assert rendered['html_body'] == ""


@pytest.mark.django_db
def test_notification_template_format_datetime(notification_template):
    notification_template.body_en = "{{ datetime|format_datetime('en') }}"
    notification_template.save()

    dt = datetime(2020, 2, 22, 12, 0, 0, 0, pytz.utc)

    context = {
        'subject_var': 'bar',
        'datetime': dt,
        'html_body_var': 'foo <b>bar</b> baz',
    }

    timezone.activate(pytz.timezone('Europe/Helsinki'))

    rendered = render_notification_template(NotificationType.TEST, context, 'en')
    assert rendered['body'] == '22 Feb 2020 at 14:00'
