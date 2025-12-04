import pytest
from django.core import mail

from helevents.tests.factories import UserFactory
from notifications.models import NotificationTemplate, NotificationType
from notifications.tests.utils import check_received_mail_exists

from ..models import PublicationStatus
from .factories import ApiKeyUserFactory, EventFactory


@pytest.fixture
def event_deleted_notification_template():
    try:
        NotificationTemplate.objects.get(
            type=NotificationType.UNPUBLISHED_EVENT_DELETED
        ).delete()
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
def test_draft_event_deleted(event_deleted_notification_template, user, event):
    event.created_by = user
    event.publication_status = PublicationStatus.DRAFT
    event.save()
    event.soft_delete()
    strings = [
        f"event deleted body, event name: {event.name}!",
    ]
    html_body = f"event deleted <b>HTML</b> body, event name: {event.name}!"
    assert len(mail.outbox) == 1
    check_received_mail_exists(
        f"event deleted subject, event name: {event.name}!",
        user.email,
        strings,
        html_body=html_body,
    )


@pytest.mark.django_db
def test_public_event_deleted_doesnt_trigger_notification(
    event_deleted_notification_template, user, event
):
    event.created_by = user
    event.save()
    event.soft_delete()
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_event_published(event_published_notification_template, user, draft_event):
    draft_event.created_by = user
    draft_event.publication_status = PublicationStatus.PUBLIC
    draft_event.save()
    strings = [
        f"event published body, event name: {draft_event.name}!",
    ]
    html_body = f"event published <b>HTML</b> body, event name: {draft_event.name}!"
    check_received_mail_exists(
        f"event published subject, event name: {draft_event.name}!",
        user.email,
        strings,
        html_body=html_body,
    )


@pytest.mark.django_db
def test_draft_posted_as_super_event_sends(
    draft_posted_notification_template, user, draft_event
):
    strings = [
        f"draft posted body, event name: {draft_event.name}!",
    ]
    html_body = f"draft posted <b>HTML</b> body, event name: {draft_event.name}!"
    check_received_mail_exists(
        f"draft posted subject, event name: {draft_event.name}!",
        user.email,
        strings,
        html_body=html_body,
    )


@pytest.mark.django_db
def test_draft_posted_created_by_admin_user_does_not_send(data_source, organization):
    admin = UserFactory()
    organization.admin_users.add(admin)
    EventFactory(
        name="testeventzor",
        data_source=data_source,
        publisher=organization,
        publication_status=PublicationStatus.DRAFT,
        created_by=admin,
    )
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_recurring_child_event_saved_does_not_send(event):
    user = UserFactory()
    event.super_event_type = event.SuperEventType.RECURRING
    EventFactory(
        name="testeventzor",
        data_source=event.data_source,
        publisher=event.publisher,
        publication_status=PublicationStatus.DRAFT,
        created_by=user,
        super_event=event,
    )
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_other_than_recurring_child_event_saved_does_send(event):
    user = UserFactory()
    EventFactory(
        name="testeventzor",
        data_source=event.data_source,
        publisher=event.publisher,
        publication_status=PublicationStatus.DRAFT,
        created_by=user,
        super_event=event,
    )
    assert len(mail.outbox) == 1


@pytest.mark.parametrize(
    "uses_api_key, expect_email",
    [
        (True, False),
        (False, True),  # Sanity check for the test
    ],
)
@pytest.mark.django_db
def test_draft_notification_is_not_sent_when_using_api_key(
    uses_api_key, expect_email, organization
):
    if uses_api_key:
        user = ApiKeyUserFactory()
        data_source = user.data_source
    else:
        user = UserFactory()
        data_source = organization.data_source
    mail.outbox = []

    EventFactory(
        data_source=data_source,
        publisher=organization,
        publication_status=PublicationStatus.DRAFT,
        created_by=user,
    )

    assert bool(mail.outbox) == expect_email
