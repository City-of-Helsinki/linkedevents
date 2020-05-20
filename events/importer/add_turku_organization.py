# -*- coding: utf-8 -*-
import logging

from django import db
from django.conf import settings
from django.core.management import call_command
from django.utils.module_loading import import_string
from django_orghierarchy.models import Organization
from django_orghierarchy.models import OrganizationClass

from events.models import DataSource, Place
from .sync import ModelSyncher
from .base import Importer, register_importer

# Per module logger
logger = logging.getLogger(__name__)

GK25_SRID = 3879


@register_importer
class OrganizationImporter(Importer):
    name = 'add_turku_organization'
    supported_languages = ['fi', 'sv']

    def setup(self):

        #public organisations model for municipalities
        '''
        #public data sourse for organisations model
        ds_args = dict(id='org', user_editable=True)
        defaults = dict(name='Ulkoa tuodut organisaatiotiedot')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)         
        
        #public organisation class for all municipalities
        ds_args = dict(origin_id='3', data_source=self.data_source)
        defaults = dict(name='Kunta')
        self.organizationclass, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)
        '''

        #city of Turku 

        #data sourse for city of Turku 
        ds_args2 = dict(id='turku', user_editable=True)
        defaults2 = dict(name='Kuntakohtainen data Turun Kaupunki')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args2)
        
        #organisation for city of Turku (check the city/munisipality number)
        org_args2 = dict(origin_id='853', data_source=self.data_source)
        defaults2 = dict(name='Turku')        
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults2, **org_args2)
       
        
        #private users (this is a Turku specific requirements for not institutional users)
        '''
        #private users public organisations class
        ds_args = dict(origin_id='11', data_source=self.data_source)
        defaults = dict(name='Yksityishenkilö')
        self.organizationclass, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

        #private users data source
        ds_args2 = dict(id='yksilo', user_editable=True)
        defaults2 = dict(name='Yksityishenkilöihin liittyvä yleisdata')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args2)
        
        #private users public organisations
        org_args2 = dict(origin_id='2000', data_source=self.data_source)
        defaults2 = dict(name='Yksityishenkilöt')        
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults2, **org_args2)
        '''

 

 
    