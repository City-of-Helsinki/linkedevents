import logging
import os
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

        # Default Image URL's.
        self.image_1, _ = Image.objects.update_or_create(
            defaults=dict(name='', photographer_name='', alt_text=''), **dict(
                license=self.cc_by_license,
                data_source=self.data_source,
                publisher=self.organization,
                url='https://kalenteri.turku.fi/sites/default/files/styles/event_node/public/images/event_ext/sadonkorjuutori.jpg'))
        self.image_2, _ = Image.objects.update_or_create(
            defaults=dict(name='', photographer_name='', alt_text=''), **dict(
                license=self.cc_by_license,
                data_source=self.data_source,
                publisher=self.organization,
                url='https://kalenteri.turku.fi/sites/default/files/styles/event_node/public/images/event_ext/img_2738.jpg'))
        self.image_3, _ = Image.objects.update_or_create(
            defaults=dict(name='', photographer_name='', alt_text=''), **dict(
                license=self.cc_by_license,
                data_source=self.data_source,
                publisher=self.organization,
                url='https://kalenteri.turku.fi/sites/default/files/styles/event_node/public/images/event_ext/66611781_2613563701989600_82393011928956928_n_7.jpg'))
        self.image_4, _ = Image.objects.update_or_create(
            defaults=dict(name='', photographer_name='', alt_text=''), **dict(
                license=self.cc_by_license,
                data_source=self.data_source,
                publisher=self.organization,
                url='https://kalenteri.turku.fi/sites/default/files/styles/event_node/public/images/event_ext/nuorten_viikonloppu_turun_seudun_tapahtumakalenterin_kuva_yhdistetty.jpg'))
