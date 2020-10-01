import logging
import os
import requests
import time
import base64
import struct
from django import db
from django.conf import settings
from django.core.management import call_command
from django.utils.module_loading import import_string
from os import mkdir
from os.path import abspath, join, dirname, exists, basename, splitext
from events.models import Image, License, DataSource
from django_orghierarchy.models import Organization, OrganizationClass
from .sync import ModelSyncher
from .base import Importer, register_importer

if not exists(join(dirname(__file__), 'logs')):
    mkdir(join(dirname(__file__), 'logs'))

logger = logging.getLogger(__name__)
curFileExt = basename(__file__)
curFile = splitext(curFileExt)[0]

logFile = \
    logging.FileHandler(
        '%s' % (join(dirname(__file__), 'logs', curFile+'.logs'))
    )
logFile.setFormatter(
    logging.Formatter(
        '[%(asctime)s] <%(name)s> (%(lineno)d): %(message)s'
    )
)
logFile.setLevel(logging.DEBUG)
logger.addHandler(
    logFile
)


@register_importer
class ImageBankImporter(Importer):
    # Class dependencies.
    name = curFile
    supported_languages = ['fi', 'sv']

    def setup(self):

        # Datasources.
        self.data_source, _ = DataSource.objects.update_or_create(
            defaults=dict(name='Kuvapankki'), **dict(id='image', user_editable=True))
        self.data_source_org, _ = DataSource.objects.update_or_create(
            defaults=dict(name='Ulkoa tuodut organisaatiotiedot'), **dict(id='org', user_editable=True))

        # Organization classes.
        self.organizationclass_kvpankki, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Kuvapankki'), **dict(origin_id='15', data_source=self.data_source_org))

        # Organizations.
        self.organization, _ = Organization.objects.update_or_create(
            defaults=dict(name='Kuvapankki'), **dict(origin_id='1500', data_source=self.data_source, classification_id='org:15'))

        try:
            self.cc_by_license = License.objects.get(id='cc_by')
        except License.DoesNotExist:
            self.cc_by_license = None

        def generate_id():
            t = time.time() * 1000000
            b = base64.b32encode(struct.pack(">Q", int(t)).lstrip(b'\x00')).strip(b'=').lower()
            return b.decode('utf8')

        IMAGE_BANK_IMAGES = {
            'https://i.imgur.com/eANHbqh.jpg',
            'https://i.imgur.com/hpF5Ugz.jpg',
            'https://i.imgur.com/nNbigmG.jpg',
            'https://i.imgur.com/e750x68.jpg'
        }

        IMAGE_BANK_IMAGES = iter(IMAGE_BANK_IMAGES)
        IMAGE_TYPE = 'jpg'
        PATH_EXTEND = 'images'

        def request_image_url():
            img = requests.get(next(IMAGE_BANK_IMAGES),
                               headers={'User-Agent': 'Mozilla/5.0'}).content
            imgfile = generate_id()
            path = '%(root)s/%(pathext)s/%(img)s.%(type)s' % ({
                'root': settings.MEDIA_ROOT,
                'pathext': PATH_EXTEND,
                'img': imgfile,
                'type': IMAGE_TYPE
            })
            with open(path, 'wb') as file:
                file.write(img)
            return '%s/%s.%s' % (PATH_EXTEND, imgfile, IMAGE_TYPE)

        # Default Image URL's.
        self.image_1, _ = Image.objects.update_or_create(
            defaults=dict(name='', photographer_name='', alt_text=''), **dict(
                license=self.cc_by_license,
                data_source=self.data_source,
                publisher=self.organization,
                image=request_image_url()))

        self.image_2, _ = Image.objects.update_or_create(
            defaults=dict(name='', photographer_name='', alt_text=''), **dict(
                license=self.cc_by_license,
                data_source=self.data_source,
                publisher=self.organization,
                image=request_image_url()))

        self.image_3, _ = Image.objects.update_or_create(
            defaults=dict(name='', photographer_name='', alt_text=''), **dict(
                license=self.cc_by_license,
                data_source=self.data_source,
                publisher=self.organization,
                image=request_image_url()))

        self.image_4, _ = Image.objects.update_or_create(
            defaults=dict(name='', photographer_name='', alt_text=''), **dict(
                license=self.cc_by_license,
                data_source=self.data_source,
                publisher=self.organization,
                image=request_image_url()))
