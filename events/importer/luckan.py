import re
import dateutil.parser
import requests
import requests_cache
import pytz
import time
from collections import OrderedDict
from django.db.models import Count

from lxml import etree

from events.models import DataSource, Place, Event, Organization, Offer
from events.models import Keyword
from events.keywords import KeywordMatcher

from .sync import ModelSyncher
from .base import Importer, register_importer, recur_dict
from .util import clean_text, unicodetext, replace_location

from django.core.management.base import BaseCommand, CommandError

LUCKAN_BASE_URL = 'https://events.osterbotten.fi/EventService/search'
LUCKAN_PARAMS = {
    'languages': OrderedDict([
        ('fi', 'fi_FI'),
        ('sv', 'sv_SE'),
        ('en', 'en_US'),
    ])
}

@register_importer
class LuckanImporter(Importer):
    name = "luckan"
    supported_languages = ['fi', 'sv', 'en']

    def __init__(self, *args, **kwargs):
        super(LuckanImporter, self).__init__(*args, **kwargs)
        self.timezone = pytz.timezone('Europe/Helsinki')

    def items_from_url(self, url):
        resp = requests.get(url)
        assert resp.status_code == 200
        root = etree.fromstring(resp.content)
        return root.xpath('Events/Event')

    def municipalities_from_url(self, url):
        resp = requests.get(url)
        assert resp.status_code == 200
        root = etree.fromstring(resp.content)
        return root.xpath('Municipalities/Municipality')

    def _import_organizers_from_events(self, events):
        organizers = recur_dict()
        for k, event in events.items():
            if not 'organizer' in event:
                continue
            organizer = event['organizer']
            if not 'name' in organizer or not 'fi' in organizer['name']:
                continue
            oid = organizer['name']['fi']
            organizers[oid]['name'].update(organizer['name'])
            organizers[oid]['phone'].update(organizer['phone'])
        return organizers

    def setup(self):
        defaults = dict(name='Luckan')
        self.data_source, _ = DataSource.objects.get_or_create(id=self.name, defaults=defaults)
        self.luckan_data_source = DataSource.objects.get(id='luckan')
        org_args = dict(id='luckan')
        defaults = dict(name='Luckan', data_source=self.data_source)
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

        if self.options['cached']:
            requests_cache.install_cache('luckan')

    def getUrl(self, locale, start):
        url = LUCKAN_BASE_URL + '?Locale=' + locale + '&Start=' + str(start)
        return url

    def import_events(self):
        self.logger.info("Importing Luckan events")
        events = recur_dict()
        keyword_matcher = KeywordMatcher()
        for lang, locale in LUCKAN_PARAMS['languages'].items():
            start = 0
            while (len( self.items_from_url( self.getUrl(locale, start) ) ) > 0):
                items = self.items_from_url( self.getUrl(locale, start) )
                start = start + 10
                for item in items:
                    self._import_event(lang, item, events, keyword_matcher)
                organizers = self._import_organizers_from_events(events)
            
        for event in events.values():
            if (event is not None):
                self.save_event(event)
        self.logger.info("%d events processed" % len(events.values()))

    def cleanCategory(self, category):
        symbols = ["&", ",", ".", "!"]
        conjunctions = [" och ", " ja ", " and "]
        conjuctionsWithSymbols = ["- och", "- ja"]

        for symbol in symbols:
            category = symbol.replace(symbol, "")
        for conjuctionsWithSymbol in conjuctionsWithSymbols:
            category = conjuctionsWithSymbol.replace(conjuctionsWithSymbol, "")
        for conjunction in conjunctions:
            category = conjunction.replace(conjunction, " ")
        
        return category

    def _import_event(self, lang, item, events, keyword_matcher):    
        eid = int(item.xpath('ID')[0].text)
        event = events[eid]
        event['data_source'] = self.data_source
        event['publisher'] = self.organization
        event['origin_id'] = eid

        event['headline'][lang] = item.xpath('Title')[0].text
        event['short_description'][lang] = item.xpath('EventTextShort')[0].text
        event['description'][lang] = item.xpath('EventText')[0].text
        event['info_url'][lang] = item.xpath('Link')[0].text

        if (item.xpath('Start')[0].text):
            startTime = dateutil.parser.parse(item.xpath('End')[0].text)
            event['start_time'] = startTime
            event['has_start_time'] = True

        if (item.xpath('End')[0].text):
            endTime = dateutil.parser.parse(item.xpath('End')[0].text)
            if (startTime <= endTime):
                event['start_time'] = endTime
                event['has_start_time'] = True

        if 'offers' not in event:
            event['offers'] = [recur_dict()]
        
        offer = event['offers'][0]
        if item.xpath('PriceType')[0].text == 'Free':
            offer['is_free'] = True
        offer['price'][lang] = item.xpath('PriceHidden')[0].text
        offer['description'][lang] = item.xpath('PriceText')[0].text

        keywords = []

        categories = item.xpath('Categories')[0]
        for category in categories:
            categoryText = category.xpath('Name')[0].text
            cleanedCategory = self.cleanCategory(categoryText)
            categorywords = cleanedCategory.split()
            
            for categoryWord in categorywords:
                _id = 'luckan:{}'.format(categoryWord.replace('/', '_'))
                if (not self.keywordExists(_id)):
                    kwargs = {
                        'id': _id,
                        'data_source_id': 'luckan',
                        'name': categoryWord,
                        'origin_id': category.xpath('ID')[0].text
                    }

                    keyword_orig, created = Keyword.objects.get_or_create(**kwargs)
                    keyword_orig.publisher = self.organization
                    keywords.append(keyword_orig)
        
        targetGroups = item.xpath('TargetGroups')[0]

        for targetGroup in targetGroups:
            targetGroupText = targetGroup.xpath('Name')[0].text
            _id = 'luckan:{}'.format(targetGroupText)
            if (not self.keywordExists(_id)):
                kwargs = {
                    'id': _id,
                    'data_source_id': 'luckan',
                    'name': targetGroupText,
                    'origin_id': category.xpath('ID')[0].text
                }

                keyword_orig, created = Keyword.objects.get_or_create(**kwargs)
                keyword_orig.publisher = self.organization
                keywords.append(keyword_orig)

        if len(keywords) > 0:
            event['keywords'] = keywords

        if 'location' not in event:
            event['location'] = recur_dict()
            
        event['location']['street_address'] = item.xpath('PostalAddress')[0].text
        event['location']['postal_code'] = item.xpath('PostalCode')[0].text
        event['location']['address_locality'] = item.xpath('Municipality')[0].text
        event['location']['publisher'] = self.organization
        event['location']['data_source'] = self.data_source

        if self.placeExists(item.xpath('Municipality')[0].get("id")):
            event['location']['id'] = 'luckan:' + item.xpath('Municipality')[0].get("id")
        else:
            self.createPlace(item.xpath('Municipality')[0].get("id"), item.xpath('Municipality')[0].text)

        return event
       
    def createPlace(self, origin_id, name):
        obj = {
            'origin_id' : origin_id,
            'id' : 'luckan:' + origin_id,
            'publisher' : self.organization,
            'data_source' : self.data_source
        }

        municipalitiesObj = {}

        for lang, locale in LUCKAN_PARAMS['languages'].items():
            municipalitiesObj[lang] = self.municipalities_from_url('https://events.osterbotten.fi/EventService/municipalities?Locale=' + locale)

        for lang, municipalitiesByLanguage in municipalitiesObj.items():
            for municipality in municipalitiesByLanguage:
                if municipality.xpath('ID')[0].text == origin_id:
                    obj['name_' + lang] = municipality.xpath('Name')[0].text
                    break
        place = Place(**obj)
        place.save()

    def keywordExists(self, _id):
        keywords = Keyword.objects.filter(id__exact='%s' % _id).order_by('id')
        keyword = keywords.first()

        if not keyword:
            return False  
        return True

    def placeExists(self, origin_id):
        municipalityId = 'luckan:' + origin_id
        places = Place.objects.filter(id__exact='%s' % municipalityId).order_by('id')
        place = places.first()

        if not place:
            return False  
        return True