import pytest
from django.conf import settings
from django.core import mail

from events.models import Feedback
from events.tests.utils import versioned_reverse as reverse

load = {
    "name": "Launchpad McQuack",
    "subject": "adventure",
    "body": "Huey, Dewey, and Louie are waiting for you Sir!",
    "email": "test@test.com",
}


@pytest.mark.django_db
def test__signed_in_user_submits(api_client, user):
    signed_url = reverse("feedback-list")
    response = api_client.post(signed_url, load, format="json")
    assert response.status_code == 401

    api_client.force_authenticate(user=user)
    response = api_client.post(signed_url, load, format="json")
    assert Feedback.objects.all().count() == 1
    assert len(mail.outbox) == 1
    assert (
        mail.outbox[0].subject
        == f"[LinkedEvents] {load['subject']} reported by {load['name']}"
    )
    assert mail.outbox[0].body == load["body"]
    assert mail.outbox[0].to == [settings.SUPPORT_EMAIL]
    assert mail.outbox[0].from_email == load["email"]


@pytest.mark.django_db
def test__guest_user_submits(api_client):
    guest_url = reverse("guest-feedback-list")
    api_client.post(guest_url, load, format="json")
    assert Feedback.objects.all().count() == 1
    assert len(mail.outbox) == 1
    assert (
        mail.outbox[0].subject
        == f"[LinkedEvents] {load['subject']} reported by {load['name']}"
    )
    assert mail.outbox[0].body == load["body"]
    assert mail.outbox[0].to == [settings.SUPPORT_EMAIL]
    assert mail.outbox[0].from_email == load["email"]
