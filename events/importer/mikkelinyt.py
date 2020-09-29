import os
import re
import requests
import requests_cache
import pytz
import logging
import hashlib

from datetime import datetime
from html.parser import HTMLParser

from events.models import DataSource, Event, Keyword
from django_orghierarchy.models import Organization

from .sync import ModelSyncher
from .base import Importer, register_importer, recur_dict

logger = logging.getLogger(__name__)

MIKKELINYT_BASE_URL = 'http://www.mikkelinyt.fi/json.php'
MIKKELINYT_API_KEY = os.getenv('MIKKELINYT_API_KEY', '')
MIKKELINYT_LOCATION = os.getenv('MIKKELINYT_LOCATION', '')
MIKKELINYT_IMAGE_BASE_URL = 'http://www.mikkelinyt.fi/uploads/savonlinnanyt'


def mark_deleted(obj):
    if obj.deleted:
        return False
    obj.deleted = True
    obj.save(update_fields=['deleted'])
    return True


@register_importer
class MikkeliNytImporter(Importer):
    name = "mikkelinyt"
    supported_languages = ['fi']

    def __init__(self, *args, **kwargs):
        super(MikkeliNytImporter, self).__init__(*args, **kwargs)
        self.timezone = pytz.timezone('Europe/Helsinki')

    def items_from_url(self, url):
        logger.info(url)

        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json()["data"]

        return None

    def setup(self):
        defaults = dict(name='MikkeliNyt')
        self.data_source, _ = DataSource.objects.get_or_create(id=self.name, defaults=defaults)
        self.mikkelinyt_data_source = DataSource.objects.get(id='mikkelinyt')
        org_args = dict(id='mikkelinyt')
        defaults = dict(name='MikkeliNyt', data_source=self.data_source)
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

        if self.options['cached']:
            requests_cache.install_cache('mikkelinyt')

    def get_url(self):
        url = MIKKELINYT_BASE_URL + '?showall=1&apiKey={}&location={}'.format(MIKKELINYT_API_KEY, MIKKELINYT_LOCATION)
        return url

    def strip_html(self, text):
        result = re.sub(r"\<.*?>", " ", text, 0, re.MULTILINE)
        result = HTMLParser().unescape(result)
        result = " ".join(result.split())
        return result.strip()

    def parse_offset_datetime(self, text):
        return datetime.strptime(text, '%Y-%m-%d %H:%M:%S').astimezone(self.timezone)

    def import_events(self):
        logger.info("Importing MikkeliNyt events")
        items = self.items_from_url(self.get_url())

        if items is None or len(items) == 0:
            logger.info("Could not parse items, giving up...")
        else:
            syncher_queryset = Event.objects.filter(
                end_time__gte=datetime.now(), data_source=self.data_source, deleted=False)
            self.syncher = ModelSyncher(syncher_queryset, lambda obj: obj.origin_id, delete_func=mark_deleted)

            for item in items:
                event = self.upsert_event(item)
                self.syncher.mark(event)

            self.syncher.finish()

    def upsert_event(self, item):
        origin_id = item["id"]
        start = self.parse_offset_datetime(item["start"])
        end = self.parse_offset_datetime(item["end"])
        description = item["description"]
        name = self.strip_html(item["name"])
        thumb = item["thumb"]
        image = item["image"]
        image_original = item["image_original"]
        url = item["url"]

        tickets = item["tickets"]
        tickets_url = item["tickets_url"]

        registration = item["registration"]

        location_origin_id = hashlib.md5(item["location"].encode('utf-8')).hexdigest()
        address = self.strip_html(item["address"])
        city = self.strip_html(item["city"])
        place = self.strip_html(item["place"])
        zipCode = self.strip_html(item["zip"])
        location = self.upsert_place(location_origin_id, address, city, place, zipCode)

        categories = item["category"]
        keywords = self.upsert_keywords(categories)

        _id = 'mikkelinyt:{}'.format(origin_id)

        external_links = []
        if registration:
            external_links.append({
                'name': 'rekisteröityminen',
                'link': registration
            })

        event = {
            'id': _id,
            'data_source': self.data_source,
            'start_time': start,
            'has_start_time': True,
            'end_time': end,
            'has_end_time': True,
            'name': {"fi": name},
            'origin_id': origin_id,
            'keywords': keywords,
            'offers': [
                {
                    'is_free': tickets == "ilmainen",
                    'description': {'fi': tickets},
                    'info_url': {'fi': tickets_url},
                    'price': None
                }
            ],
            'description': {
                "fi": description
            },
            'short_description': {
                "fi": description
            },
            'location': location,
            'publisher': self.organization,
            'info_url': {
                'fi': url
            },
            'images': [{
                'name': 'thumb',
                'url': thumb
            }, {
                'name': 'image',
                'url': image
            }, {
                'name': 'image_original',
                'url': image_original
            }],
            'external_links': {
                'fi': external_links
            }
        }

        return self.save_event(event)

    def upsert_keywords(self, categories):
        keywords = []

        for category in categories:
            origin_id = category["id"]
            name = category["name"]
            keyword = self.upsert_keyword(origin_id, name)
            keywords.append(keyword)

        return keywords

    def upsert_keyword(self, origin_id, name):
        _id = 'mikkelinyt:{}'.format(origin_id)

        kwargs = {
            'id': _id,
            'data_source_id': 'mikkelinyt',
            'name_fi': name,
            'origin_id': origin_id,
            'publisher': self.organization
        }

        Keyword.objects.get_or_create(**kwargs)

        keywords = Keyword.objects.filter(id__exact='%s' % _id).order_by('id')
        return keywords.first()

    def upsert_place(self, origin_id, address, city, place, zipCode):
        result = recur_dict()
        _id = 'mikkelinyt:{}'.format(origin_id)

        result['id'] = _id
        result['origin_id'] = origin_id
        result['name']['fi'] = place
        result['street_address']['fi'] = address
        result['postal_code'] = zipCode
        result['address_locality']['fi'] = city
        result['publisher'] = self.organization
        result['data_source'] = self.data_source

        self.save_place(result)

        return result
