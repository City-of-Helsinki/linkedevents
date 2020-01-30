# -*- coding: utf-8 -*-
import pytest
from rest_framework.exceptions import ValidationError
from events.models import Offer, EventLink, Video


@pytest.mark.django_db
def test_event_cannot_have_deprecated_keyword(event, keyword):
    keyword.deprecated = True
    keyword.save()
    event.keywords.set([keyword])
    with pytest.raises(ValidationError):
        event.save()
    event.keywords.set([])
    event.audience.set([keyword])
    with pytest.raises(ValidationError):
        event.save()


@pytest.mark.django_db
def test_event_remap_relations_on_replace(event, event2, event3, languages):
    offer = Offer.objects.create(event=event, price='price')
    link = EventLink.objects.create(
        event=event, name='eventlink', language=languages[0], link='https://link.to.url')
    video = Video.objects.create(event=event, name='video', url='https://link.to.video')
    event3.super_event = event
    event3.save()

    event.replaced_by = event2
    event.save()
    assert event.offers.count() == 0
    assert event.external_links.count() == 0
    assert event.videos.count() == 0
    assert event.sub_events.count() == 0
    assert offer in event2.offers.all()
    assert link in event2.external_links.all()
    assert video in event2.videos.all()
    assert event3 in event2.sub_events.all()
