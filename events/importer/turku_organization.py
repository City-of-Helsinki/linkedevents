# -> Dev notes: 13/08/2020:
# 
# Turku Organization importer for importing all Turku Organization data such as Datasources, Organizations, Organization Classes and support for Virtual Events.
# Contains the latest Turku Linkedevents Organization Model.
# Logger implementation added.

#Dependencies
import logging
import os

from django import db
from django.conf import settings
from django.core.management import call_command
from django.utils.module_loading import import_string
from django_orghierarchy.models import Organization
from django_orghierarchy.models import OrganizationClass
from os import mkdir
from os.path import abspath, join, dirname, exists, basename, splitext
from events.models import DataSource, Place
from .sync import ModelSyncher
from .base import Importer, register_importer

if not exists(join(dirname(__file__), 'logs')):
    mkdir(join(dirname(__file__), 'logs'))

__setattr__ = setattr
__iter__ = iter
__next__ = next


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


def get_create_ds(ob, args):
    try:
        ds, _ = DataSource.objects.update_or_create(defaults=args[1], **args[0])
        return ds
    except:
        logger.warn("DataSource update_or_create did NOT pass: "+ob+" correctly. Argument/Arguments incompatible.")

def get_create_organization(ob, args):
    try:
        org, _ = Organization.objects.update_or_create(defaults=args[1], **args[0])
        return org
    except:
        logger.warn("Organization update_or_create did NOT pass: "+ob+" correctly. Argument/Arguments incompatible.")

def get_create_organizationclass(ob, args):
    try:
        orgclass, _ = OrganizationClass.objects.update_or_create(defaults=args[1], **args[0])
        return orgclass
    except:
        logger.warn("OrganizationClass update_or_create did NOT pass: "+ob+" correctly. Argument/Arguments incompatible.")

def get_create_place(ob, args):
    try:
        placey, _ = Place.objects.update_or_create(defaults=args[1], **args[0])
        return placey
    except:
        logger.warn("Place update_or_create did NOT pass: "+ob+" correctly. Argument/Arguments incompatible.")

def preprocess():
    #DataSource
    # -> datasources contains all top level datasource objects; no data_source defined. 
    datasources = {
        'system':[dict(id=settings.SYSTEM_DATA_SOURCE_ID, user_editable=True), dict(name='Järjestelmän sisältä luodut lähteet')],
        'org':[dict(id="org", user_editable=True), dict(name='Ulkoa tuodut organisaatiotiedot')],
        'turku':[dict(id="turku", user_editable=True), dict(name='Kuntakohtainen data Turun Kaupunki')],
        'yksilo':[dict(id="yksilo", user_editable=True), dict(name='Yksityishenkilöihin liittyvä yleisdata')],
        'virtual':[dict(id="virtual", user_editable=True), dict(name='Virtuaalitapahtumat.')]
    }
    return_ds = [get_create_ds(keys, values) for keys, values in datasources.items()]

    #OrganizationClass
    # -> ds_orgs_class contains all objects with a data_source component.
    ds_orgs_class = {
        'valttoim':[dict(origin_id='1', data_source=return_ds[1]), dict(name='Valtiollinen toimija')],
        'maaktoim':[dict(origin_id='2', data_source=return_ds[1]), dict(name='Maakunnallinen toimija')],
        'kunta':[dict(origin_id='3', data_source=return_ds[1]), dict(name='Kunta')],
        'kunnanliik':[dict(origin_id='4', data_source=return_ds[1]), dict(name='Kunnan liikelaitos')],
        'valtliik':[dict(origin_id='5', data_source=return_ds[1]), dict(name='Valtion liikelaitos')],
        'yrityss':[dict(origin_id='6', data_source=return_ds[1]), dict(name='Yritys')],
        'saatioo':[dict(origin_id='7', data_source=return_ds[1]), dict(name='Säätiö')],
        'seurakuntaa':[dict(origin_id='8', data_source=return_ds[1]), dict(name='Seurakunta')],
        'yhdseurr':[dict(origin_id='9', data_source=return_ds[1]), dict(name='Yhdistys tai seura')],
        'muuyhtt':[dict(origin_id='10', data_source=return_ds[1]), dict(name='Muu yhteisö')],
        'ykshenkk':[dict(origin_id='11', data_source=return_ds[1]), dict(name='Yksityishenkilö')],
        'paiktietoo':[dict(origin_id='12', data_source=return_ds[1]), dict(name='Paikkatieto')],
        'sanastoo':[dict(origin_id='13', data_source=return_ds[1]), dict(name='Sanasto')],
        'virtuaalitapahh':[dict(origin_id='14', data_source=return_ds[1]), dict(name='Virtuaalitapahtuma')],
    }
    return_orgclass_ds = [get_create_organizationclass(keys, values) for keys, values in ds_orgs_class.items()]
    # ds_orgs_class needs a datasource get value, hence why return_ds[0] -
    # has to be used after the iteration and two separate iterations are required.
    rds = return_ds.__iter__()
    rgc = return_orgclass_ds.__iter__()

    #Organizations
    org_arr = {
        'turku_org':[dict(origin_id='853', data_source=return_ds[2], classification_id="org:3"), dict(name='Turun kaupunki')],
        'ykshenkilöt':[dict(origin_id='2000', data_source=return_ds[3], classification_id="org:11"), dict(name='Yksityishenkilöt')],
        'org_virtual':[dict(origin_id='3000', data_source=return_ds[4], classification_id="org:14"), dict(name='Virtuaalitapahtumat')],
    }
    return_org = [get_create_organization(keys, values) for keys, values in org_arr.items()]
    ro = return_org.__iter__()

    #Organization level 2 and level 3 are both part of the new linkedevents organization model.
    org_level_2 = {
        'konsernipalv':[dict(origin_id='04', data_source=return_ds[2], parent=return_org[0], classification_id="org:3"), dict(name='Konsernihallinto ja palvelukeskukset')],
        'varsaluepel':[dict(origin_id='12', data_source=return_ds[2], parent=return_org[0], classification_id="org:3"), dict(name='Varsinais-Suomen aluepelastuslaitos')],
        'hyvinvointitoimi':[dict(origin_id='25', data_source=return_ds[2], parent=return_org[0], classification_id="org:3"), dict(name='Hyvinvointitoimiala')],
        'sivistys':[dict(origin_id='40', data_source=return_ds[2], parent=return_org[0], classification_id="org:3"), dict(name='Sivistystoimiala')],
        'vapaatoim':[dict(origin_id='44', data_source=return_ds[2], parent=return_org[0], classification_id="org:3"), dict(name='Vapaa-aikatoimiala')],
        'kaupunkiymprst':[dict(origin_id='61', data_source=return_ds[2], parent=return_org[0], classification_id="org:3"), dict(name='Kaupunkiympäristötoimiala')],
        'tkukaupteatteri':[dict(origin_id='80', data_source=return_ds[2], parent=return_org[0], classification_id="org:3"), dict(name='Turun Kaupunginteatteri')],
    }
    return_org_level_2 = [get_create_organization(keys, values) for keys, values in org_level_2.items()]
    rot2 = return_org_level_2.__iter__()

    org_level_3 = {
        'matkpalvelukesk':[dict(origin_id='0719', data_source=return_ds[2], parent=return_org_level_2[0], classification_id="org:3"), dict(name='Matkailun palvelukeskus')],
        'työllisyyspalvkesk':[dict(origin_id='0720', data_source=return_ds[2], parent=return_org_level_2[0], classification_id="org:3"), dict(name='Työllisyyspalvelukeskus')],
        'amk':[dict(origin_id='4032', data_source=return_ds[2], parent=return_org_level_2[3], classification_id="org:3"), dict(name='Ammatillinen koulutus')],
        'lukiokoul':[dict(origin_id='4031', data_source=return_ds[2], parent=return_org_level_2[3], classification_id="org:3"), dict(name='Lukiokoulutus')],
        'kirjastopalv':[dict(origin_id='4453', data_source=return_ds[2], parent=return_org_level_2[4], classification_id="org:3"), dict(name='Kirjastopalvelut')],
        'liikuntpalv':[dict(origin_id='4470', data_source=return_ds[2], parent=return_org_level_2[4], classification_id="org:3"), dict(name='Liikuntapalvelut')],
        'museopalv':[dict(origin_id='4462', data_source=return_ds[2], parent=return_org_level_2[4], classification_id="org:3"), dict(name='Museopalvelut')],
        'nuorisopalv':[dict(origin_id='4480', data_source=return_ds[2], parent=return_org_level_2[4], classification_id="org:3"), dict(name='Nuorisopalvelut')],
        'turunkaupunginork':[dict(origin_id='4431', data_source=return_ds[2], parent=return_org_level_2[4], classification_id="org:3"), dict(name='Turun Kaupunginorkesteri')]
    }
    return_org_level_3 = [get_create_organization(keys, values) for keys, values in org_level_3.items()]
    rot3 = return_org_level_3.__iter__()

    #Place
    place_arr = {
        'place_org_virtual':[dict(id='virtual:public', origin_id='public', data_source=return_ds[4]),
        dict(data_source=return_ds[4],
        publisher=return_org[1],
        name='Virtuaalitapahtuma',
        name_fi='Virtuaalitapahtuma',
        name_sv='Virtuell evenemang',
        name_en='Virtual event',
        description='Toistaiseksi kaikki virtuaalitapahtumat merkitään tähän paikkatietoon.')]
    }

    return_place_org = [get_create_place(keys, values) for keys, values in place_arr.items()]
    rpo = return_place_org.__iter__()

    try:
        return { # -> Class attribute names go here. Could return an already sorted dictionary if need be.
            'data_source_system': rds.__next__(),
            'data_source_org': rds.__next__(),
            'organization_class_1': rgc.__next__(),
            'organization_class_2': rgc.__next__(),
            'organization_class_3': rgc.__next__(),
            'organization_class_4': rgc.__next__(),
            'organization_class_5': rgc.__next__(),
            'organization_class_6': rgc.__next__(),
            'organization_class_7': rgc.__next__(),
            'organization_class_8': rgc.__next__(),
            'organization_class_9': rgc.__next__(),
            'organization_class_10': rgc.__next__(),
            'organization_class_11': rgc.__next__(),
            'organization_class_12': rgc.__next__(),
            'organization_class_13': rgc.__next__(),
            'organization_class_14': rgc.__next__(),
            'data_source': rds.__next__(),
            'organization': ro.__next__(),
            'organization_1': ro.__next__(),
            'organization_2': ro.__next__(),
            'internet_location': rpo.__next__(),
            'orgtaso2': rot2.__next__(),
            'orgtaso2_1': rot2.__next__(),
            'orgtaso2_2': rot2.__next__(),
            'orgtaso2_3': rot2.__next__(),
            'orgtaso2_4': rot2.__next__(),
            'orgtaso2_5': rot2.__next__(),
            'orgtaso2_6': rot2.__next__(),
            'orgtaso3': rot3.__next__(),
            'orgtaso3_1': rot3.__next__(),
            'orgtaso3_2': rot3.__next__(),
            'orgtaso3_3': rot3.__next__(),
            'orgtaso3_4': rot3.__next__(),
            'orgtaso3_5': rot3.__next__(),
            'orgtaso3_6': rot3.__next__(),
            'orgtaso3_7': rot3.__next__(),
            'orgtaso3_8': rot3.__next__(),
        }
    except: 
        logger.warn("Stop iteration error when returning preprocess function items.")


@register_importer
class OrganizationImporter(Importer):
    #name and supported_languages are dependencies that the OrganizationImporter class requires.
    name = curFile #curFile is defined up top. It's the name of this current file.
    supported_languages = ['fi', 'sv']
    def setup(self):
        for k, v in preprocess().items():
            __setattr__(self, k, v)
            logger.info("OrganizationImporter attribute created: "+k)