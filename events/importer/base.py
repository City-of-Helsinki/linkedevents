import os
import logging
import itertools

from util import partial_copy, partial_equals

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
        for example different nights of the same play."""
        getname = lambda x: x['name']['fi']
        events = sorted(events, key=getname)
        for name_fi, subevents in itertools.groupby(events, getname):
            subevents = list(subevents)
            if(len(subevents) < 2): continue
            potential_parent = partial_copy(subevents[0], instance_fields)
            children_found = False
            for matching_event in (
                    itertools.ifilter(
                        lambda e: partial_equals(
                            e, potential_parent, instance_fields),
                        subevents)):
                for k in matching_event.keys():
                    if k not in instance_fields: del matching_event[k]
                matching_event['parent_event'] = potential_parent
            if subevents[0].get('parent_event') is not None:
                events.append(potential_parent)
        return events

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
