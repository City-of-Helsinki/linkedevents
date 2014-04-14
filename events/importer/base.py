import os
import re
import logging
import itertools
from collections import defaultdict

from django.db import DataError
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings

from modeltranslation.translator import translator

from .util import active_language
from events.models import *


def place_not_found(data_source, pid):
    return ('Place not found', (str(data_source), str(pid)))

# Using a recursive default dictionary
# allows easy updating of the same data keys
# with different languages on different passes.
def recur_dict(): return defaultdict(recur_dict)

class Importer(object):
    def __init__(self, options):
        super(Importer, self).__init__()
        self.options = options
        self.verbosity = options['verbosity']
        self.logger = logging.getLogger(__name__)

        importer_langs = set(self.supported_languages)
        configured_langs = set(l[0] for l in settings.LANGUAGES)
        # Intersection is all the languages possible for the importer to use.
        self.languages = {}
        for lang_code in importer_langs & configured_langs:
            # FIXME: get language name translations from Django
            lang_obj, _ = Language.objects.get_or_create(id=lang_code)
            self.languages[lang_code] = lang_obj
        self.setup()

    def setup(self):
        pass

    @staticmethod
    def clean_text(text):
        text = text.replace('\n', ' ')
        # remove consecutive whitespaces
        return re.sub(r'\s\s+', ' ', text, re.U).strip()

    @staticmethod
    def unicodetext(item):
        s = item.text
        if not s:
            return None
        return Importer.clean_text(s)

    @staticmethod
    def text(item, tag):
        return unicodetext(item.find(matko_tag(tag)))

    def link_recurring_events(self, events, instance_fields=[]):
        """Finds events that are instances of a common parent
        event by comparing the fields that do not differ between
        instances, for example different nights of the same play.

        Returns a list of events."""

        def event_name(e):
            # recur_dict ouch
            if not 'fi' in e['common']['name']:
                return ''
            else:
                return e['common']['name']['fi']

        events.sort(key=event_name)
        parent_events = []
        for name_fi, subevents in itertools.groupby(events, event_name):
            subevents = list(subevents)
            if (len(subevents) < 2):
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

    def save_location(self, location_dict):
        location_dict.default_factory = None
        postal_address, created = PostalAddress.objects.get_or_create(
            street_address_fi=location_dict['address']['street_address']['fi'],
            address_locality_fi=location_dict['address']['address_locality']['fi'],
            postal_code=location_dict['address'].get('postal_code')
        )
        place, created = Place.objects.get_or_create(
            data_source=location_dict['data_source'],
            origin_id=location_dict['origin_id']
        )
        place.address = postal_address
        geodata = location_dict.get('geo')
        if geodata:
            place.geo = GeoInfo(**geodata)
        else:
            place.geo = GeoInfo()

        for l, _ in settings.LANGUAGES:
            with active_language(l):
                name = location_dict['name']
                if l in name:
                    place.name = name[l]
                for key in ['email', 'street_address', 'address_locality']:
                    val = location_dict['address'][key]
                    if l in val:
                        setattr(postal_address, key, val[l])

        place.save()
        place.geo.save()
        postal_address.save()


    def _set_field(self, obj, field_name, val):
        if not hasattr(obj, field_name):
            print(vars(obj))
        if getattr(obj, field_name) == val:
            return
        setattr(obj, field_name, val)
        obj._changed = True


    def save_event(self, event):
        errors = set()

        args = dict(data_source=event['data_source'], origin_id=event['origin_id'])
        try:
            obj = Event.objects.get(**args)
            obj._created = False
        except Event.DoesNotExist:
            obj = Event(**args)
            obj._created = True
        obj._changed = False

        obj_fields = list(obj._meta.fields)
        trans_fields = translator.get_options_for_model(Event).fields
        skip_fields = ['id', 'location', 'offers', 'category']

        for field_name, lang_fields in trans_fields.items():
            lang_fields = list(lang_fields)
            for lf in lang_fields:
                lang = lf.language
                # Do not process this field later
                skip_fields.append(lf.name)

                if field_name not in event:
                    continue

                data = event[field_name]
                if lang in data:
                    val = data[lang]
                else:
                    val = None
                self._set_field(obj, lf.name, val)

            # Remove original translated field
            skip_fields.append(field_name)

        for d in skip_fields:
            for f in obj_fields:
                if f.name == d:
                    obj_fields.remove(f)
                    break

        if 'origin_id' in event:
            event['origin_id'] = str(event['origin_id'])

        for field in obj_fields:
            field_name = field.name
            if field_name not in event:
                continue
            self._set_field(obj, field_name, event[field_name])

        location_id = None
        if 'location' in event:
            location = event['location']
            if 'id' in location:
                location_id = location['id']
        self._set_field(obj, 'location_id', location_id)

        if obj._changed or obj._created:
            if obj._created:
                verb = "created"
            else:
                verb = "changed"
            print("%s %s" % (obj, verb))
            obj.save()

        if 'category' in event:
           for c in event['category']:
               obj.categories.add(c)

        return errors


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
