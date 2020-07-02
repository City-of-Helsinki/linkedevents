from django.core.management import BaseCommand

from events.models import Keyword


class Command(BaseCommand):
    help = "Update keyword has_upcoming_events field"

    def handle(self, **kwargs):
        Keyword.objects.has_upcoming_events_update()
        print('Keywords updated')
