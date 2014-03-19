import os
import logging
import itertools

from django.db import DataError
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings

from util import active_language
from events.models import Event, PostalAddress

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

        event_name = lambda e: e['common']['name']['fi']
        events = sorted(events, key=event_name)
        parent_events = []
        for name_fi, subevents in itertools.groupby(events, event_name):
            subevents = list(subevents)
            if(len(subevents) < 2):
                parent_events.extend(subevents)
                continue
            potential_parent = subevents[0]
            is_subevent = lambda e: (
                e['common'] == potential_parent['common'])
            children = []
            for matching_event in filter(is_subevent, subevents):
                children.append(matching_event['instance'])
            if len(children) > 0:
                potential_parent['children'] = children
                parent_events.append(potential_parent)
        return parent_events

    def save_children_through_parent(self, parent_dict):
        model_values = parent_dict['common']
        model_values.default_factory = None

        no_children = len(parent_dict['children']) < 1
        if no_children:
            model_values.update(parent_dict['instance'])

        data_source = model_values['data_source']

        # Try to find the possible existing parent
        # in the database.
        if no_children:
            parent, created = Event.objects.get_or_create(
                origin_id=model_values['origin_id'],
                data_source=data_source
            )
        else:
            children_ids = [c['origin_id'] for c in parent_dict['children']]
            try:
                child = Event.objects.filter(
                    data_source=data_source
                ).filter(
                    origin_id__in=children_ids
                ) [0]
                parent = child.super_event
            except IndexError:
                parent = Event()

        remove_keys = [
            'types', # todo: add to model
            'organizer', # todo: add to model
            'matko_location_id', # todo: add to model
        ]
        for key in remove_keys: model_values.pop(key, None)

        trans_fields = {key: None for key in ['name', 'description', 'url']}
        for key in trans_fields.iterkeys():
            value = model_values.pop(key, None)
            if value is not None:
                trans_fields[key] = value

        for key, value in model_values.iteritems():
            setattr(parent, key, value)
        for l, _ in settings.LANGUAGES:
            with active_language(l):
                for key, value in trans_fields.iteritems():
                    if value and l in value:
                        setattr(parent, key, value[l])

        parent.save()

        for child_dict in parent_dict['children']:
            origin_id = child_dict.get('origin_id')
            del child_dict['origin_id']
            del child_dict['matko_location_id']
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
