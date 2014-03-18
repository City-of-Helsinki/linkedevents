import os
import logging
import itertools

from django.db import DataError
from django.conf import settings

from util import copy_without_keys, partial_equals, active_language
from events.models import Event

class Importer(object):
    def __init__(self, options):
        super(Importer, self).__init__()
        self.options = options
        self.logger = logging.getLogger(__name__)
        self.setup()

    def setup(self):
        pass

    def link_recurring_events(self, events, instance_fields=[]):
        """Finds events that are instances of a common parent
        event by comparing the fields that do not differ between
        instances, for example different nights of the same play.

        Returns a list of events."""

        event_name = lambda e: e['name']['fi']
        events = sorted(events, key=event_name)
        parent_events = []
        for name_fi, subevents in itertools.groupby(events, event_name):
            subevents = list(subevents)
            if(len(subevents) < 2):
                parent_events.extend(subevents)
                continue
            potential_parent = copy_without_keys(subevents[0], instance_fields)
            is_subevent = lambda e: (
                partial_equals(e, potential_parent, instance_fields))

            children = []
            for matching_event in (filter(is_subevent, subevents)):
                for k in matching_event.keys():
                    if k not in instance_fields: del matching_event[k]
                children.append(matching_event)

            if len(children) > 0:
                potential_parent['children'] = children
                parent_events.append(potential_parent)
        return parent_events

    def save_children_through_parent(self, parent_dict):
        model_values = copy_without_keys(
            parent_dict, [
                'children',
                'name', 'description', 'url', # translatable fields
                'types', # todo: add to model
                'organizer', # todo: add to model
                'matko_location_id', # todo: add to model
            ])
        parent = Event(**model_values)

        for l, _ in settings.LANGUAGES:
            with active_language(l):
                for key in ['name', 'description', 'url']:
                    field = parent_dict[key]
                    if l in field: setattr(parent, key, field[l])

        children_ids = [c['origin_id'] for c in parent_dict['children']]
        try:
            child = Event.objects.filter(origin_id__in=children_ids)[0]
            parent.id = child.super_event.id
        except IndexError:
            pass

        parent.save()

        for child_dict in parent_dict['children']:
            origin_id = child_dict.get('origin_id')
            del child_dict['origin_id']
            Event.objects.get_or_create(
                origin_id=origin_id,
                super_event=parent,
                data_source=parent.data_source,
                defaults = child_dict)

importers = {}

def register_importer(klass):
    importers[klass.name] = klass
    return klass

def get_importers():
    if importers:
        return importers
    # Importing the packages will cause their register_importer() methods
    # being called.
    for fname in os.listdir(os.path.dirname(__file__)):
        module, ext = os.path.splitext(fname)
        if ext.lower() != '.py':
            continue
        if module in ('__init__', 'base'):
            continue
        full_path = "%s.%s" % (__package__, module)
        ret = __import__(full_path, locals(), globals())
    return importers
