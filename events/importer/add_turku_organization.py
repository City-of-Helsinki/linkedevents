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

#GK23_SRID = 3877#SRID is not use on this importer (this not use geo spatial library)


@register_importer
class OrganizationImporter(Importer):
    name = 'add_turku_organization'
    supported_languages = ['fi', 'sv']

    def setup(self):
        #system data source

        ds_args0 = dict(id=settings.SYSTEM_DATA_SOURCE_ID, user_editable=True)
        defaults0 = dict(name='Järjestelmän sisältä luodut lähteet')
        self.data_source_system, _ = DataSource.objects.get_or_create(defaults=defaults0, **ds_args0)
        
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
        '''    
        #data sourse for city of Turku 
        ds_args2 = dict(id='turku', user_editable=True)
        defaults2 = dict(name='Kuntakohtainen data Turun Kaupunki')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args2)
        
        #organisation for city of Turku (check the city/munisipality number)
        org_args2 = dict(origin_id='853', data_source=self.data_source)
        defaults2 = dict(name='Turku')        
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults2, **org_args2)
        '''
        
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
        '''
        1 Valtiollinen toimija 		 (events_datasource:org)
        2 Maakunnallinen toimija
        3 Kunta
        4 Kunnan liikelaitos
        5 Valtion liikelaitos
        6 Yritys
        7 Säätiö
        8 Seurakunta
        9 Yhdistys tai seura
        10 Muu yhteisö
        11 Yksityishenkilö
        12 Paikkatieto
        13 Sanasto
        14 Virtuaalitapahtuma
        '''
        #public data sources

        #public data sourse for organisations model
        ds_args1 = dict(id='org', user_editable=True)
        defaults1 = dict(name='Ulkoa tuodut organisaatiotiedot')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults1, **ds_args1)  

        #public organizations classes   

        #public organizations class for all instans 
        ds_args = dict(origin_id='1', data_source=self.data_source)
        defaults = dict(name='Valtiollinen toimija')
        self.organizationclass1, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

        #public organizations class for all instans 
        ds_args = dict(origin_id='2', data_source=self.data_source)
        defaults = dict(name='Maakunnallinen toimija')
        self.organizationclass2, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

        #public organizations class for all instans 
        ds_args = dict(origin_id='3', data_source=self.data_source)
        defaults = dict(name='Kunta')
        self.organizationclass3, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

        #public organizations class for all instans 
        ds_args = dict(origin_id='4', data_source=self.data_source)
        defaults = dict(name='Kunnan liikelaitos')
        self.organizationclass4, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)
        
        #public organizations class for all instans 
        ds_args = dict(origin_id='5', data_source=self.data_source)
        defaults = dict(name='Valtion liikelaitos')
        self.organizationclass5, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

        #public organizations class for all instans 
        ds_args = dict(origin_id='6', data_source=self.data_source)
        defaults = dict(name='Yritys')
        self.organizationclass6, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

        #public organizations class for all instans 
        ds_args = dict(origin_id='7', data_source=self.data_source)
        defaults = dict(name='Säätiö')
        self.organizationclass7, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)
        
        #public organizations class for all instans 
        ds_args = dict(origin_id='8', data_source=self.data_source)
        defaults = dict(name='Seurakunta')
        self.organizationclass8, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

        #public organizations class for all instans 
        ds_args = dict(origin_id='9', data_source=self.data_source)
        defaults = dict(name='Yhdistys tai seura')
        self.organizationclass9, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

        #public organizations class for all instans
        ds_args = dict(origin_id='10', data_source=self.data_source)
        defaults = dict(name='Muu yhteisö')
        self.organizationclass10, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

        #public organizations class for all instans (this includes also city of Turku specifig organization class)
        ds_args = dict(origin_id='11', data_source=self.data_source)
        defaults = dict(name='Yksityishenkilö')
        self.organizationclass11, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

           #public organizations class for all instans (this includes also city of Turku specifig organization class)
        ds_args = dict(origin_id='12', data_source=self.data_source)
        defaults = dict(name='Paikkatieto')
        self.organizationclass12, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

           #public organizations class for all instans (this includes also city of Turku specifig organization class)
        ds_args = dict(origin_id='13', data_source=self.data_source)
        defaults = dict(name='Sanasto')
        self.organizationclass13, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)
        
        #public organizations class for all instans 
        ds_args = dict(origin_id='14', data_source=self.data_source)
        defaults = dict(name='Virtuaalitapahtuma')
        self.organizationclass14, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)
        

        #city of Turku 
            
        #data sourse for city of Turku 
        ds_args2 = dict(id='turku', user_editable=True)
        defaults2 = dict(name='Kuntakohtainen data Turun Kaupunki')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults2, **ds_args2)
        
        #organisation for city of Turku (check the city/munisipality number)
        org_args2 = dict(origin_id='853', data_source=self.data_source)
        defaults2 = dict(name='Turku')        
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults2, **org_args2)
        

        #public organizations and it's data source

            #private users

        #private users data source (this includes also city of Turku specifig organization)
        ds_args3 = dict(id='yksilo', user_editable=True)
        defaults3 = dict(name='Yksityishenkilöihin liittyvä yleisdata')
        self.data_source, _ = DataSource.objects.get_or_create(defaults=defaults3, **ds_args3)
        
        #private users public organisations (this includes also city of Turku specifig organization)
        org_args3 = dict(origin_id='2000', data_source=self.data_source, classification_id.)
        defaults3 = dict(name='Yksityishenkilöt')        
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults3, **org_args3)
        
            #Virtual events

        #Virtual events data source 
        ds_args4 = dict(id='virtual', user_editable=True)
        defaults4 = dict(name='Virtuaalitapahtumat (ei paikkaa, vain URL)')
        self.data_source_virtual, _ = DataSource.objects.get_or_create(defaults=defaults4, **ds_args4)
        
        #Virtual events public organisations
        org_args4 = dict(origin_id='3000', data_source=self.data_source_virtual)
        defaults4 = dict(name='Virtuaalitapahtumat')        
        self.organization_virtual, _ = Organization.objects.get_or_create(defaults=defaults4, **org_args4)

        # "Etätapahtumat" are mapped to our new fancy "Tapahtuma vain internetissä." location
        print(self.data_source_virtual)
        VIRTUAL_LOCATION_ID = str(self.data_source_virtual) + ':public'

        # Create "Tapahtuma vain internetissä" location if not present
        defaults5 = dict(data_source=self.data_source_virtual,
                        publisher=self.organization_virtual,
                        name='Virtuaalitapahtuman paikka',
                        #description='Tapahtuma vain internetissä.',)
                        description='Toistaiseksi kaikki virtuaalitapahtumat merkitään tähän paikkatietoon.',)
        self.internet_location, _ = Place.objects.get_or_create(id=VIRTUAL_LOCATION_ID, defaults=defaults5)

    