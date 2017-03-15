from django.core.management import BaseCommand
from django.db import transaction

from events.models import Keyword, recache_n_events


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        with transaction.atomic():
            keywords = Keyword.objects.all()
            for kw in keywords:
                recache_n_events(kw)
            print(keywords.count())
