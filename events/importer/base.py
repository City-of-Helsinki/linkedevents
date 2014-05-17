import os
import re
import logging
import itertools
from collections import defaultdict

from django.db import DataError
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.gdal import SpatialReference, CoordTransform

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

        self.target_srid = settings.PROJECTION_SRID
        gps_srs = SpatialReference(4326)
        target_srs = SpatialReference(self.target_srid)
        if getattr(settings, 'BOUNDING_BOX'):
            self.bounding_box = Polygon.from_bbox(settings.BOUNDING_BOX)
            self.bounding_box.set_srid(self.target_srid)
            target_to_gps_ct = CoordTransform(target_srs, gps_srs)
            self.bounding_box.transform(target_to_gps_ct)
        else:
            self.bounding_box = None
        self.gps_to_target_ct = CoordTransform(gps_srs, target_srs)

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

    def _set_field(self, obj, field_name, val):
        if not hasattr(obj, field_name):
            print(vars(obj))
        obj_val = getattr(obj, field_name)
        if obj_val == val:
            return
        setattr(obj, field_name, val)
        obj._changed = True

    def _update_fields(self, obj, info, skip_fields):
        obj_fields = list(obj._meta.fields)
        trans_fields = translator.get_options_for_model(type(obj)).fields
        for field_name, lang_fields in trans_fields.items():
            lang_fields = list(lang_fields)
            for lf in lang_fields:
                lang = lf.language
                # Do not process this field later
                skip_fields.append(lf.name)

                if field_name not in info:
                    continue

                data = info[field_name]
                if data is not None and lang in data:
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

        if 'origin_id' in info:
            info['origin_id'] = str(info['origin_id'])

        for field in obj_fields:
            field_name = field.name
            if field_name not in info:
                continue
            self._set_field(obj, field_name, info[field_name])

    def save_event(self, info):
        info = info.copy()

        args = dict(data_source=info['data_source'], origin_id=info['origin_id'])
        try:
            obj = Event.objects.get(**args)
            obj._created = False
        except Event.DoesNotExist:
            obj = Event(**args)
            obj._created = True
        obj._changed = False

        location_id = None
        location_extra_info = None
        if 'location' in info:
            location = info['location']
            if 'id' in location:
                location_id = location['id']
            info['location_extra_info'] = location.get('extra_info', None)

        skip_fields = ['id', 'location', 'offers', 'keywords']
        self._update_fields(obj, info, skip_fields)

        self._set_field(obj, 'location_id', location_id)

        if obj._created or obj._changed:
            obj.save()

        keywords = info.get('keywords', [])
        new_keywords = set([kw.id for kw in keywords])
        old_keywords = set(obj.keywords.values_list('id', flat=True))
        if new_keywords != old_keywords:
            obj.keywords = new_keywords
            obj._changed = True

        if obj._changed or obj._created:
            if obj._created:
                verb = "created"
            else:
                verb = "changed"
            print("%s %s" % (obj, verb))

    def save_place(self, info):
        errors = set()

        args = dict(data_source=info['data_source'], origin_id=info['origin_id'])
        try:
            obj = Place.objects.get(**args)
            obj._created = False
        except Place.DoesNotExist:
            obj = Place(**args)
            obj._created = True
        obj._changed = False

        skip_fields = ['id', 'position', 'custom_fields']
        self._update_fields(obj, info, skip_fields)

        n = info.get('latitude', 0)
        e = info.get('longitude', 0)
        position = None
        if n and e:
            p = Point(e, n, srid=4326) # GPS coordinate system
            if p.within(self.bounding_box):
                if self.target_srid != 4326:
                    p.transform(self.gps_to_target_ct)
                position = p
            else:
                print("Invalid coordinates (%f, %f) for %s" % (n, e, obj))

        if position and obj.position:
            # If the distance is less than 10cm, assume the position
            # hasn't changed.
            assert obj.position.srid == settings.PROJECTION_SRID
            if position.distance(obj.position) < 0.10:
                position = obj.position
        if position != obj.position:
            obj._changed = True
            obj.position = position

        if obj._changed or obj._created:
            if obj._created:
                verb = "created"
            else:
                verb = "changed"
            print("%s %s" % (obj, verb))
            obj.save()

        return obj

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
