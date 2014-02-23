import re
import dateutil.parser
import requests
import requests_cache
from lxml import etree

from .sync import ModelSyncher
from .base import Importer, register_importer

MATKO_URLS = {
    'locations': {
        'fi': 'http://www.visithelsinki.fi/misc/feeds/helsinki_matkailu_poi.xml',
        'en': 'http://www.visithelsinki.fi/misc/feeds/helsinki_tourism_poi.xml',
        'sv': 'http://www.visithelsinki.fi/misc/feeds/helsingfors_turism_poi.xml',
    },
    'events': {
        'fi': 'http://www.visithelsinki.fi/misc/feeds/kaikkitapahtumat.xml',
        'en': 'http://www.visithelsinki.fi/misc/feeds/kaikkitapahtumat_en.xml',
        'sv': 'http://www.visithelsinki.fi/misc/feeds/kaikkitapahtumat_se.xml',
    }
}

def clean_text(text):
    text = text.replace('\n', ' ')
    # remove consecutive whitespaces
    return re.sub(r'\s\s+', ' ', text, re.U).strip()

def matko_tag(tag):
    return '{https://aspicore-asp.net/matkoschema/}' + tag

@register_importer
class MatkoImporter(Importer):
    name = "matko"

    def _import_events_from_feed(self, lang_code, items):
        for item in items:
            title = clean_text(item.find('title').text)
            print title.encode('utf8')
            start_time = dateutil.parser.parse(item.find(matko_tag('starttime')).text)
            print start_time

    def import_events(self):
        print("Importing Matko events")
        url = MATKO_URLS['events']['fi']
        requests_cache.install_cache('matko')
        resp = requests.get(url)
        assert resp.status_code == 200
        root = etree.fromstring(resp.content)
        items = root.xpath('channel/item')
        self._import_events_from_feed('fi', items)
        pass

    def import_locations(self):
        print("Importing Matko locations")
        pass
