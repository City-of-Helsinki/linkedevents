import os
import logging
import itertools
import datetime
import pytz
from collections import defaultdict
from functools import partial
import operator

from django.conf import settings
from rest_framework.exceptions import ValidationError
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.gdal import SpatialReference, CoordTransform

from events.importer.sync import ModelSyncher
from .util import separate_scripts, clean_text

from modeltranslation.translator import translator

from events.models import Image, Language, Event, Offer, EventLink, Place

# Per module logger
logger = logging.getLogger(__name__)

EXTENSION_COURSE_FIELDS = ('enrolment_start_time', 'enrolment_end_time', 'maximum_attendee_capacity',
                           'minimum_attendee_capacity', 'remaining_attendee_capacity')
LOCAL_TZ = pytz.timezone(settings.TIME_ZONE)


# Using a recursive default dictionary
# allows easy updating of the same data keys
# with different languages on different passes.
def recur_dict():
    return defaultdict(recur_dict)


class Importer(object):
    def __init__(self, options):
        super(Importer, self).__init__()
        self.options = options

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
            self.bounding_box.srid = self.target_srid
            target_to_gps_ct = CoordTransform(target_srs, gps_srs)
            self.bounding_box.transform(target_to_gps_ct)
        else:
            self.bounding_box = None
        self.gps_to_target_ct = CoordTransform(gps_srs, target_srs)

        self.setup()

        # this has to be run after setup, as it relies on organization and data source being set
        self._images = {obj.url: obj for obj in Image.objects.filter(publisher=self.organization,
                                                                     data_source=self.data_source)}

    def setup(self):
        pass

    @staticmethod
    def _set_multiscript_field(string, event, languages, field):
        """
        Will overwrite the event field in specified languages with any paragraphs
        in those languages discovered in string.

        :param string: The string of paragraphs to process.
        :param event: The event to update
        :param languages: An iterable of desired languages, preferred language first.
        :param field: The field to update
        :return:
        """
        different_scripts = separate_scripts(string, languages)
        for script, string in different_scripts.items():
            if string:
                event[field][script] = string

    def set_image(self, obj, image_data):
        if not image_data:
            self._set_field(obj, 'image', None)
            return

        image_url = image_data.get('url', '').strip()
        if not image_url:
            print('Invalid image url "{}" obj {}'.format(image_data.get('url'), obj))
            return

        image = self._get_image(image_url)
        image = self._update_image(image, image_data)
        self._set_field(obj, 'image', image)

        if image._changed:
            obj._changed = True
            obj._changed_fields.append('image')

    def set_images(self, obj, images_data):
        image_syncher = ModelSyncher(obj.images.all(),
                                     lambda image: image.url,
                                     delete_func=partial(self._remove_image, obj))

        for image_data in images_data:
            image_url = image_data.get('url', '').strip()
            if not image_url:
                print('Invalid image url "{}" obj {}'.format(image_data.get('url'), obj))
                continue

            new_image = False
            image = image_syncher.get(image_url)

            if not image:
                new_image = True
                image = self._get_image(image_url)

            image = self._update_image(image, image_data)

            if new_image:
                obj.images.add(image)
                obj._changed = True
                obj._changed_fields.append('images')
            elif image._changed:
                obj._changed = True
                obj._changed_fields.append('images')

            image_syncher.mark(image)

        image_syncher.finish(force=True)

    def _remove_image(self, obj, image):
        # we need this to mark the object changed if an image is removed
        obj._changed = True
        obj._changed_fields.append('images')
        obj.images.remove(image)
        return True

    def _get_image(self, image_url):
        if not image_url:
            return None

        if image_url in self._images:
            return self._images[image_url]

        image = Image(
            publisher=self.organization,
            data_source=self.data_source,
            url=image_url,
        )
        self._images[image_url] = image
        image._changed = True
        image._created = True

        return image

    def _update_image(self, image, image_data):
        if not hasattr(image, '_changed'):
            image._changed = False

        self._set_field(image, 'publisher', self.organization)
        self._set_field(image, 'data_source', self.data_source)

        for field in ('name', 'photographer_name', 'cropping', 'license', 'alt_text'):
            if field in image_data:
                self._set_field(image, field, image_data.get(field))

        if image._changed:
            image.save()

        return image

    def link_recurring_events(self, events, instance_fields=[]):
        """Finds events that are instances of a common parent
        event by comparing the fields that do not differ between
        instances, for example different nights of the same play.

        Returns a list of events."""

        def event_name(e):
            # recur_dict ouch
            if 'fi' not in e['common']['name']:
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
            children = []
            for matching_event in (e for e in subevents if e['common'] == potential_parent['common']):
                children.append(matching_event['instance'])
            if len(children) > 0:
                potential_parent['children'] = children
                parent_events.append(potential_parent)
        return parent_events

    def _set_field(self, obj, field_name, val):
        if not hasattr(obj, field_name):
            logger.debug(vars(obj))
        obj_val = getattr(obj, field_name, None)
        # this prevents overwriting manually edited values with empty values
        if obj_val == val or (hasattr(obj, 'is_user_edited') and obj.is_user_edited() and not val):
            return
        setattr(obj, field_name, val)
        obj._changed = True
        if not hasattr(obj, '_changed_fields'):
            obj._changed_fields = []
        obj._changed_fields.append(field_name)

    def _save_field(self, obj, obj_field_name, info,
                    info_field_name, max_length=None):
        
        if type(info[info_field_name]) == None:
            print('Type none: ', info_field_name, ': ', info[info_field_name])
        else:            
            # atm only used by place importers, do some extra cleaning and validation before setting value
            if info_field_name in info:
                val = clean_text(info[info_field_name])
            else:
                val = None
            if max_length and val and len(val) > max_length:
                self.logger.warning("%s: field %s too long" % (obj, info_field_name))
                val = None
            self._set_field(obj, obj_field_name, val)

    def _save_translated_field(self, obj, obj_field_name, info,
                               info_field_name, max_length=None):
        # atm only used by place importers, do some extra cleaning and validation before setting value
        for lang in self.supported_languages:
            key = '%s_%s' % (info_field_name, lang)
            obj_key = '%s_%s' % (obj_field_name, lang)

            self._save_field(obj, obj_key, info, key, max_length)
            if lang == 'fi':
                self._save_field(obj, obj_field_name, info, key, max_length)

    # multilevel (3 step max) json version for turku 
    def _save_field_multilevel(self, obj, obj_field_name, info,
                     info_field_name, max_length=None, nodeNames=[], lang=''):
        # atm only used by place importers, do some extra cleaning and validation before setting value
        # multilevel (6 step max) json version for turku 
        #print ('lang: ', lang) 
        if info_field_name in info:
            if len(nodeNames) == 0 and lang == '':
                #print ('LEVEL1 no lang: ', info[info_field_name])
                val = clean_text(info[info_field_name])
            elif len(nodeNames) == 0:
                #print ('LEVEL1: ', info[info_field_name][lang], ' lang: ', lang)
                val = clean_text(info[info_field_name][lang])
            if len(nodeNames) == 1 and lang == '':                
                #print ('LEVEL2 CCC no lang: ', info[info_field_name][nodeNames])
                val = clean_text(info[info_field_name][nodeNames[0]])
            elif len(nodeNames) == 1:
                #print ('LEVEL2: ', info[info_field_name][nodeNames[0]][lang] , ' lang: ', lang) 
                val = clean_text(info[info_field_name][nodeNames[0]][lang])
            if len(nodeNames) == 2 and lang == '':
                val = clean_text(info[info_field_name][nodeNames[0]][nodeNames[1]])
            elif len(nodeNames) == 2:
                val = clean_text(info[info_field_name][nodeNames[0]][nodeNames[1]][lang])
            if len(nodeNames) == 3 and lang == '':
                val = clean_text(info[info_field_name][nodeNames[0]][nodeNames[1]][nodeNames[2]])
            elif len(nodeNames) == 3:
                val = clean_text(info[info_field_name][nodeNames[0]][nodeNames[1]][nodeNames[2]][lang])
            if len(nodeNames) == 4 and lang == '': 
                val = clean_text(info[info_field_name][nodeNames[0]][nodeNames[1]][nodeNames[2]][nodeNames[3]])    
            elif len(nodeNames) == 4: 
                val = clean_text(info[info_field_name][nodeNames[0]][nodeNames[1]][nodeNames[2]][nodeNames[3]][lang])
            if len(nodeNames) == 5 and lang == '': 
                val = clean_text(info[info_field_name][nodeNames[0]][nodeNames[1]][nodeNames[2]][nodeNames[3]][nodeNames[4]])
            elif len(nodeNames) == 5: 
                val = clean_text(info[info_field_name][nodeNames[0]][nodeNames[1]][nodeNames[2]][nodeNames[3]][nodeNames[4]][lang])
            if len(nodeNames) > 5:
                self.logger.warning("%s: field %s Check level of nodes! Max main level + 5 + lang" % (obj, info_field_name))     
        else:
            val = None
        if max_length and val and len(val) > max_length:
            self.logger.warning("%s: field %s too long" % (obj, info_field_name))
            val = None
        self._set_field(obj, obj_field_name, val)

    # multilevel (3 step max) json version for turku 
    def _save_translated_field_multilevel(self, obj, obj_field_name, info,
                               info_field_name, max_length=None, nodeNames=[]):
        # atm only used by place importers, do some extra cleaning and validation before setting value
        # multilevel (6 step max) json version for turku 
        for lang in self.supported_languages:
            #key = '%s_%s' % (info_field_name, lang)

            obj_key = '%s_%s' % (obj_field_name, lang)
            #print ('AAAA obj_key saving on field: ', obj_key)
            #print ('BBBB and this language: ', lang)

            self._save_field_multilevel(obj, obj_key, info, info_field_name, max_length, nodeNames, lang)
            if lang == 'fi':
                self._save_field_multilevel(obj, obj_field_name, info, info_field_name, max_length, nodeNames, lang)
            
            #self.logger.warning("%s: field %s Check level of nodes!" % (obj, info_field_name)) 

    def _update_fields(self, obj, info, skip_fields):
        # all non-place importers use this method, automatically takes care of translated fields
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
        obj_id = "%s:%s" % (info['data_source'].id, info['origin_id'])
        try:
            obj = Event.objects.get(**args)
            obj._created = False
            assert obj.id == obj_id
        except Event.DoesNotExist:
            obj = Event(**args)
            obj._created = True
            obj.id = obj_id
        obj._changed = False
        obj._changed_fields = []

        location_id = None
        if 'location' in info:
            location = info['location']
            if 'id' in location:
                location_id = location['id']
            if 'extra_info' in location:
                info['location_extra_info'] = location['extra_info']

        assert info['start_time']
        if 'has_start_time' not in info:
            info['has_start_time'] = True
        if not info['has_start_time']:
            # Event start time is not exactly defined.
            # Use midnight in event timezone, or, if given in utc, local timezone
            if info['start_time'].tzinfo == pytz.utc:
                info['start_time'] = info['start_time'].astimezone(LOCAL_TZ)
            info['start_time'] = info['start_time'].replace(hour=0, minute=0, second=0)

        # If no end timestamp supplied, we treat the event as ending at midnight.
        if 'end_time' not in info or not info['end_time']:
            info['end_time'] = info['start_time']
            info['has_end_time'] = False

        if 'has_end_time' not in info:
            info['has_end_time'] = True

        # If end date is supplied but no time, the event ends at midnight of the following day.
        if not info['has_end_time']:
            # Event end time is not exactly defined.
            # Use midnight in event timezone, or, if given in utc, local timezone
            if info['end_time'].tzinfo == pytz.utc:
                info['end_time'] = info['start_time'].astimezone(LOCAL_TZ)
            info['end_time'] = info['end_time'].replace(hour=0, minute=0, second=0)
            info['end_time'] += datetime.timedelta(days=1)

        skip_fields = ['id', 'location', 'publisher', 'offers', 'keywords', 'images']
        self._update_fields(obj, info, skip_fields)

        self._set_field(obj, 'location_id', location_id)

        self._set_field(obj, 'publisher_id', info['publisher'].id)

        self._set_field(obj, 'deleted', False)

        if obj._created:
            # We have to save new objects here to be able to add related fields.
            # Changed objects will be saved only *after* related fields have been changed.
            try:
                obj.save()
            except ValidationError as error:
                logger.error('Event {} could not be saved: {}'.format(obj, error))
                raise

        # many-to-many fields

        if 'images' in info:
            self.set_images(obj, info['images'])

        keywords = info.get('keywords', [])
        new_keywords = set([kw.id for kw in keywords])
        old_keywords = set(obj.keywords.values_list('id', flat=True))
        if new_keywords != old_keywords:
            if obj.is_user_edited():
                # this prevents overwriting manually added keywords
                if not new_keywords <= old_keywords:
                    obj.keywords.add(*new_keywords)
                    obj._changed = True
            else:
                obj.keywords.set(new_keywords)
                obj._changed = True
            obj._changed_fields.append('keywords')
        audience = info.get('audience', [])
        new_audience = set([kw.id for kw in audience])
        old_audience = set(obj.audience.values_list('id', flat=True))
        if new_audience != old_audience:
            if obj.is_user_edited():
                # this prevents overwriting manually added audience
                if not new_audience <= old_audience:
                    obj.audience.add(*new_audience)
                    obj._changed = True
            else:
                obj.audience.set(new_audience)
                obj._changed = True
            obj._changed_fields.append('audience')
        in_language = info.get('in_language', [])
        new_languages = set([lang.id for lang in in_language])
        old_languages = set(obj.in_language.values_list('id', flat=True))
        if new_languages != old_languages:
            if obj.is_user_edited():
                # this prevents overwriting manually added languages
                if not new_languages <= old_languages:
                    obj.in_language.add(*new_languages)
                    obj._changed = True
            else:
                obj.in_language.set(in_language)
                obj._changed = True
            obj._changed_fields.append('in_language')

        # one-to-many fields with foreign key pointing to event

        offers = []
        for offer in info.get('offers', []):
            offer_obj = Offer(event=obj)
            self._update_fields(offer_obj, offer, skip_fields=['id'])
            offers.append(offer_obj)

        val = operator.methodcaller('simple_value')
        if set(map(val, offers)) != set(map(val, obj.offers.all())):
            # this prevents overwriting manually added offers. do not update offers if we have added ones
            if not obj.is_user_edited() or len(set(map(val, offers))) >= obj.offers.count():
                obj.offers.all().delete()
                for o in offers:
                    o.save()
                obj._changed = True
                obj._changed_fields.append('offers')

        links = []
        if 'external_links' in info:
            for lang in info['external_links'].keys():
                for l in info['external_links'][lang]:
                    l['language'] = lang
                links += info['external_links'][lang]

        # TODO: use simple_value logic like for offers above?
        def obj_make_link_id(obj):
            return '%s:%s:%s' % (obj.language_id, obj.name, obj.link)

        def info_make_link_id(info):
            return '%s:%s:%s' % (info['language'], info.get('name', ''), info['link'])

        new_links = set([info_make_link_id(link) for link in links])
        old_links = set([obj_make_link_id(link) for link in obj.external_links.all()])
        if old_links != new_links:
            # this prevents overwriting manually added links. do not update links if we have added ones
            if not obj.is_user_edited() or len(new_links) >= len(old_links):
                obj.external_links.all().delete()
                for link in links:
                    link_obj = EventLink(event=obj, language_id=link['language'], link=link['link'])
                    if len(link['link']) > 200:
                        continue
                    if 'name' in link:
                        link_obj.name = link['name']
                    link_obj.save()
                obj._changed = True
                obj._changed_fields.append('links')

        if 'extension_course' in settings.INSTALLED_APPS:
            extension_data = info.get('extension_course')
            if extension_data is not None:
                from extension_course.models import Course

                try:
                    course = obj.extension_course
                    course._changed = False
                    for field in EXTENSION_COURSE_FIELDS:
                        self._set_field(course, field, extension_data.get(field))

                    course_changed = course._changed
                    if course_changed:
                        course.save()

                except Course.DoesNotExist:
                    Course.objects.create(
                        event=obj,
                        **{field: extension_data.get(field) for field in EXTENSION_COURSE_FIELDS}
                    )
                    course_changed = True

                if course_changed:
                    obj._changed = True
                    obj._changed_fields.append('extension_course')

        # If event start time changed, it was rescheduled.
        if 'start_time' in obj._changed_fields:
            self._set_field(obj, 'event_status', Event.Status.RESCHEDULED)

        if obj._changed or obj._created:
            # Finally, we must save the whole object, even when only related fields changed.
            # Also, we want to log all that happened.
            try:
                obj.save()
            except ValidationError as error:
                print('Event ' + str(obj) + ' could not be saved: ' + str(error))
                raise
            if obj._created:
                verb = "created"
            else:
                verb = "changed (fields: %s)" % ', '.join(obj._changed_fields)
            logger.debug("{} {}".format(obj, verb))

        return obj

    def save_place(self, info):
        args = dict(data_source=info['data_source'], origin_id=info['origin_id'])
        obj_id = "%s:%s" % (info['data_source'].id, info['origin_id'])
        try:
            obj = Place.objects.get(**args)
            obj._created = False
            assert obj.id == obj_id
        except Place.DoesNotExist:
            obj = Place(**args)
            obj._created = True
            obj.id = obj_id
        obj._changed = False

        skip_fields = ['id', 'position', 'custom_fields', 'publisher']
        self._update_fields(obj, info, skip_fields)

        n = info.get('latitude', 0)
        e = info.get('longitude', 0)
        position = None
        if n and e:
            p = Point(e, n, srid=4326)  # GPS coordinate system
            if p.within(self.bounding_box):
                if self.target_srid != 4326:
                    p.transform(self.gps_to_target_ct)
                position = p
            else:
                logger.warning("Invalid coordinates (%f, %f) for %s" % (n, e, obj))

        if position and obj.position:
            # If the distance is less than 10cm, assume the position
            # hasn't changed.
            assert obj.position.srid == settings.PROJECTION_SRID
            if position.distance(obj.position) < 0.10:
                position = obj.position
        if position != obj.position:
            obj._changed = True
            obj.position = position

        # we may end up reinstating deleted locations whenever they are imported back and forth
        if obj.deleted:
            obj.deleted = False
            obj._changed = True

        self._set_field(obj, 'publisher_id', info['publisher'].id)

        if obj._changed or obj._created:
            if obj._created:
                verb = "created"
            else:
                verb = "changed"
            logger.debug("%s %s" % (obj, verb))
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
