# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
from django.utils.text import slugify
from django.conf import settings
import dateutil.parser
from pytz import timezone

from .base import Importer, register_importer, recur_dict
from events.models import DataSource, Event, Organization

LOCAL_TZ = timezone('Europe/Helsinki')

@register_importer
class MantyharjuImporter(Importer):
    name = "mantyharju"
    supported_languages = ['fi']

    def setup(self):
        ds_args = dict(id=self.name)
        defaults = dict(name='Mäntyharju')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        org_args = dict(id='mantyharju:87fefd9e-0d06-46d5-ab14-a4a35fa03b17')
        defaults = dict(name='Mäntyharju', data_source=self.data_source)
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

    def _import_event(self, lang, event_data, events):
        eid = slugify(event_data['title'])
        if (len(eid) > 30):
            eid = eid[:30]
        event = events[eid]
        event['data_source'] = self.data_source
        event['publisher'] = self.organization
        event['origin_id'] = eid

        event['headline'][lang] = event_data['title']
        event['name'][lang] = event_data['title']
        event['short_description'][lang] = event_data['description']
        event['description'][lang] = event_data['description']

        if (event_data['start']):
            start_time = dateutil.parser.parse(event_data['start'])
            start_time = start_time.astimezone(LOCAL_TZ)
            event['has_start_time'] = True
            #event['has_end_time'] = True
            event['start_time'] = start_time
            #event['end_time'] = start_time
        else:
            event['start_time'] = None

        return True

    def import_events(self):
        print("Importing Mantyharju events")
        if settings.FLUSH_BEFORE_IMPORT:
            Event.objects.all().delete()
        events = recur_dict()
        import_path = settings.MANTYHARJU_JSON_PATH
        with open(import_path, 'r') as events_file:
            events_data = json.load(events_file)
            for event_data in events_data:
                success = self._import_event('fi', event_data, events)

            for eid, event in events.items():
                self.save_event(event)
