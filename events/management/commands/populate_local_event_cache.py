from datetime import datetime

import pytz
from django.core.cache import caches
from django.core.management import BaseCommand

from events.models import Event
from linkedevents.settings import MUNIGEO_MUNI


class Command(BaseCommand):
    help = "Update local ongoing and upcoming events cache."

    def handle(self, *args, **options):
        cache = caches['ongoing_local']

        local_events = Event.objects.filter(location__divisions__ocd_id__endswith=MUNIGEO_MUNI,
                                            end_time__gte=datetime.utcnow().replace(tzinfo=pytz.utc),
                                            deleted=False,
                                            ).values_list('id', 'name', 'description', 'short_description',
                                                          'name_en', 'description_en', 'short_description_en',
                                                          'name_sv', 'description_sv', 'short_description_sv',
                                                          'keywords__name_fi', 'keywords__name_sv', 'keywords__name_en',  # noqa E501
                                                          'location__street_address_fi', 'location__street_address_sv',
                                                          'location__name_fi', 'location__name_sv', 'location__name_en',  # noqa E501
                                                          'location__description_fi', 'location__description_sv',
                                                          'location__description_en')
        event_dict = {i[0]: set() for i in local_events}
        for i in local_events:
            event_dict[i[0]].update(i[1:])
            event_dict[i[0]].discard(None)

        event_strings = {k: " ".join(v) for k, v in event_dict.items()}

        cache.set('ids', event_strings)
