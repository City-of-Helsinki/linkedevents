import os
import logging
import itertools

from django.db import DataError

from util import partial_copy, partial_equals
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

        Returns pair of (parent events, normal events)"""

        event_name = lambda x: x['name']['fi']
        events = sorted(events, key=event_name)
        parent_events = []
        for name_fi, subevents in itertools.groupby(events, event_name):
            subevents = list(subevents)
            if(len(subevents) < 2): continue
            potential_parent = partial_copy(subevents[0], instance_fields)
            children = []
            for matching_event in (
                    itertools.ifilter(
                        lambda e: partial_equals(
                            e, potential_parent, instance_fields),
                        subevents)):
                for k in matching_event.keys():
                    if k not in instance_fields: del matching_event[k]
                matching_event['parent_event'] = potential_parent
                children.append(matching_event)
            if len(children) > 0:
                potential_parent['children'] = children
                parent_events.append(potential_parent)
        return parent_events, events

    def save_children_through_parent(self, parent_dict):
        children_ids = [c['same_as'] for c in parent_dict['children']]

        # todo: add proper fields below
        del parent_dict['source']
        del parent_dict['link']
        del parent_dict['types']
        del parent_dict['children']
        if 'organizer' in parent_dict: del parent_dict['organizer']
        del parent_dict['matko_location_id']
        # todo: add proper fields above

        for key in ['name', 'description']:
            for lang, val in parent_dict[key].items():
                parent_dict[key + '_' + lang] = val
            del parent_dict[key]
        
        parent = Event(**parent_dict)

        existing_parent_id = None
        for child in Event.objects.filter(same_as__in=children_ids):
            # Todo: ensure previously
            # separate super events haven't been merged in new
            # version of source data (theoretical?).
            existing_parent_id = child.super_event.id
#            parent.children.add(child)

        if existing_parent_id is not None:
            parent.id =  existing_parent_id

        parent.save()

    def save_event(self, event_dict):
        same_as = event_dict.get('same_as')
        del event_dict['same_as']
        Event.objects.get_or_create(
            same_as=same_as,
            defaults = event_dict)

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
