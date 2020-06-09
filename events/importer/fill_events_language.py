# -*- coding: utf-8 -*-
import logging

from django import db
from django.conf import settings
from django.core.management import call_command, BaseCommand, CommandError
from django.utils.module_loading import import_string
from django_orghierarchy.models import Organization


from django.db import transaction


from events.models import Language
from .sync import ModelSyncher
from .base import Importer, register_importer

# Per module logger
logger = logging.getLogger(__name__)

#this importer fills events_language table fields (the table has already be but there is id's only)

@register_importer
class LanguageFiedsImporter(Importer):
    name = 'fill_events_language'
    supported_languages = ['fi', 'sv']
  

    def setup(self):

        self.organization = '' 
        self.data_source = ''
   
        LANGUAGE_SET_DATA = [{
            'id': 'fi',
            'name': 'Suomi',
            'name_fi': 'Suomi',
            'name_sv': 'Finska',
            'name_en': 'Finnish',
        },
        {
            'id': 'sv',
            'name': 'Ruotsi',
            'name_fi': 'Ruotsi',
            'name_sv': 'Svenska',
            'name_en': 'Swedish',
        },
        {
            'id': 'en',
            'name': 'Englanti',
            'name_fi': 'Englanti',
            'name_sv': 'Engelska',
            'name_en': 'English',
        }]

        
        for i in LANGUAGE_SET_DATA:
            language, created = Language.objects.update_or_create(id=i['id'], defaults= i)
       
            if created:
                print('New language %s (%s)' % (i['name_fi'], i['id']))
            else:
                print('Language %s (%s) already exists and it is updated now.' % (i['name_fi'], i['id']))

