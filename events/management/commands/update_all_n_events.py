from django.core.management import BaseCommand
from django.db import transaction

from events.models import Keyword
from events.sql import count_events_for_keywords


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        with transaction.atomic():
            Keyword.objects.update(n_events=0)
            for keyword_id, n_events in count_events_for_keywords().items():
                Keyword.objects.filter(id=keyword_id).update(n_events=n_events)
