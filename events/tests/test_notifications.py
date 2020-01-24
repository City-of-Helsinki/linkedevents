# -*- coding: utf-8 -*-

import pytest

from ..models import PublicationStatus
from notifications.models import NotificationTemplate, NotificationType
from notifications.tests.utils import check_received_mail_exists


@pytest.fixture
def event_deleted_notification_template():
    try:
        NotificationTemplate.objects.get(type=NotificationType.UNPUBLISHED_EVENT_DELETED).delete()
    except NotificationTemplate.DoesNotExist:
        pass
    template = NotificationTemplate.objects.create(
        type=NotificationType.UNPUBLISHED_EVENT_DELETED,
        subject="event deleted subject, event name: {{ event.name }}!",
        body="event deleted body, event name: {{ event.name }}!",
        html_body="event deleted <b>HTML</b> body, event name: {{ event.name }}!",
    )
    return template


@pytest.fixture
def event_published_notification_template():
    try:
        NotificationTemplate.objects.get(type=NotificationType.EVENT_PUBLISHED).delete()
    except NotificationTemplate.DoesNotExist:
        pass
    template = NotificationTemplate.objects.create(
        type=NotificationType.EVENT_PUBLISHED,
        subject="event published subject, event name: {{ event.name }}!",
        body="event published body, event name: {{ event.name }}!",
        html_body="event published <b>HTML</b> body, event name: {{ event.name }}!",
    )
    return template


@pytest.fixture
def draft_posted_notification_template():
    try:
        NotificationTemplate.objects.get(type=NotificationType.DRAFT_POSTED).delete()
    except NotificationTemplate.DoesNotExist:
        pass
    template = NotificationTemplate.objects.create(
        type=NotificationType.DRAFT_POSTED,
        subject="draft posted subject, event name: {{ event.name }}!",
        body="draft posted body, event name: {{ event.name }}!",
        html_body="draft posted <b>HTML</b> body, event name: {{ event.name }}!",
    )
    return template


@pytest.mark.django_db
def test_unpublished_event_deleted(event_deleted_notification_template, user, event):
    event.created_by = user
    event.save()
    event.soft_delete()
    strings = [
        "event deleted body, event name: %s!" % event.name,
    ]
    html_body = "event deleted <b>HTML</b> body, event name: %s!" % event.name
    check_received_mail_exists(
        "event deleted subject, event name: %s!" % event.name, user.email, strings, html_body=html_body)


@pytest.mark.django_db
def test_event_published(event_published_notification_template, user, draft_event):
    draft_event.created_by = user
    draft_event.publication_status = PublicationStatus.PUBLIC
    draft_event.save()
    strings = [
        "event published body, event name: %s!" % draft_event.name,
    ]
    html_body = "event published <b>HTML</b> body, event name: %s!" % draft_event.name
    check_received_mail_exists(
        "event published subject, event name: %s!" % draft_event.name, user.email, strings, html_body=html_body)


@pytest.mark.django_db
def test_draft_posted(draft_posted_notification_template, user, draft_event):
    strings = [
        "draft posted body, event name: %s!" % draft_event.name,
    ]
    html_body = "draft posted <b>HTML</b> body, event name: %s!" % draft_event.name
    check_received_mail_exists(
        "draft posted subject, event name: %s!" % draft_event.name, user.email, strings, html_body=html_body)
