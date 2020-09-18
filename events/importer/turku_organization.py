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
class OrganizationImporter(Importer):
    # Class dependencies.
    name = curFile
    supported_languages = ['fi', 'sv']

    def setup(self):

        # Datasources.
        self.data_source, _ = DataSource.objects.update_or_create(
            defaults=dict(name='Järjestelmän sisältä luodut lähteet'), **dict(id=settings.SYSTEM_DATA_SOURCE_ID, user_editable=True))
        self.data_source_org, _ = DataSource.objects.update_or_create(
            defaults=dict(name='Ulkoa tuodut organisaatiotiedot'), **dict(id='org', user_editable=True))
        self.data_source_turku, _ = DataSource.objects.update_or_create(
            defaults=dict(name='Kuntakohtainen data Turun Kaupunki'), **dict(id='turku', user_editable=True))
        self.data_source_yksilo, _ = DataSource.objects.update_or_create(
            defaults=dict(name='Yksityishenkilöihin liittyvä yleisdata'), **dict(id='yksilo', user_editable=True))
        self.data_source_virtual, _ = DataSource.objects.update_or_create(
            defaults=dict(name='Virtuaalitapahtumat'), **dict(id='virtual', user_editable=True))

        # Organization classes.
        self.organizationclass_valtiollinen_toimija, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Valtiollinen toimija'), **dict(origin_id='1', data_source=self.data_source_org))
        self.organizationclass_maakunnallinen_toimija, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Maakunnallinen toimija'), **dict(origin_id='2', data_source=self.data_source_org))
        self.organizationclass_kunta, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Kunta'), **dict(origin_id='3', data_source=self.data_source_org))
        self.organizationclass_kunnan_liikelaitos, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Kunnan liikelaitos'), **dict(origin_id='4', data_source=self.data_source_org))
        self.organizationclass_valtion_liikelaitos, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Valtion liikelaitos'), **dict(origin_id='5', data_source=self.data_source_org))
        self.organizationclass_yritys, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Yritys'), **dict(origin_id='6', data_source=self.data_source_org))
        self.organizationclass_saatio, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Säätiö'), **dict(origin_id='7', data_source=self.data_source_org))
        self.organizationclass_seurakunta, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Seurakunta'), **dict(origin_id='8', data_source=self.data_source_org))
        self.organizationclass_yhdistys_seura, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Yhdistys tai seura'), **dict(origin_id='9', data_source=self.data_source_org))
        self.organizationclass_muu_yhteiso, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Muu yhteisö'), **dict(origin_id='10', data_source=self.data_source_org))
        self.organizationclass_yksityis_henkilo, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Yksityishenkilö'), **dict(origin_id='11', data_source=self.data_source_org))
        self.organizationclass_paikkatieto, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Paikkatieto'), **dict(origin_id='12', data_source=self.data_source_org))
        self.organizationclass_sanasto, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Sanasto'), **dict(origin_id='13', data_source=self.data_source_org))
        self.organizationclass_virtuaalitapahtuma, _ = OrganizationClass.objects.update_or_create(
            defaults=dict(name='Virtuaalitapahtuma'), **dict(origin_id='14', data_source=self.data_source_org))

        # Organizations.
        self.organization, _ = Organization.objects.update_or_create(
            defaults=dict(name='Turun kaupunki'), **dict(origin_id='853', data_source=self.data_source_turku, classification_id='org:3'))
        self.organization_yksityis, _ = Organization.objects.update_or_create(
            defaults=dict(name='Yksityishenkilöt'), **dict(origin_id='2000', data_source=self.data_source_yksilo, classification_id='org:11'))
        self.organization_virtual, _ = Organization.objects.update_or_create(
            defaults=dict(name='Virtuaalitapahtumat'), **dict(origin_id='3000', data_source=self.data_source_virtual, classification_id='org:14'))

        # Organization Level 2 (Part of new Turku Organization Model).
        self.orglevel2_koserni_palvelukesk, _ = Organization.objects.update_or_create(
            defaults=dict(name='Konsernihallinto ja palvelukeskukset'), **dict(origin_id='04', data_source=self.data_source_turku, parent=self.organization, classification_id='org:3'))
        self.orglevel2_varsinais_aluepelaitos, _ = Organization.objects.update_or_create(
            defaults=dict(name='Varsinais-Suomen aluepelastuslaitos'), **dict(origin_id='12', data_source=self.data_source_turku, parent=self.organization, classification_id='org:3'))
        self.orglevel2_hyvinvointitoim, _ = Organization.objects.update_or_create(
            defaults=dict(name='Hyvinvointitoimiala'), **dict(origin_id='25', data_source=self.data_source_turku, parent=self.organization, classification_id='org:3'))
        self.orglevel2_sivistystoim, _ = Organization.objects.update_or_create(
            defaults=dict(name='Sivistystoimiala'), **dict(origin_id='40', data_source=self.data_source_turku, parent=self.organization, classification_id='org:3'))
        self.orglevel2_vapaa_aikatoim, _ = Organization.objects.update_or_create(
            defaults=dict(name='Vapaa-aikatoimiala'), **dict(origin_id='44', data_source=self.data_source_turku, parent=self.organization, classification_id='org:3'))
        self.orglevel2_kaupunkiymparistotoim, _ = Organization.objects.update_or_create(
            defaults=dict(name='Kaupunkiympäristötoimiala'), **dict(origin_id='61', data_source=self.data_source_turku, parent=self.organization, classification_id='org:3'))
        self.orglevel2_turun_kaupunginteatteri, _ = Organization.objects.update_or_create(
            defaults=dict(name='Turun Kaupunginteatteri'), **dict(origin_id='80', data_source=self.data_source_turku, parent=self.organization, classification_id='org:3'))

        # Organization Level 3 (Part of new Turku Organization Model).
        self.orglevel3_matkpalvelukesk, _ = Organization.objects.update_or_create(
            defaults=dict(name='Matkailun palvelukeskus'), **dict(origin_id='0719', data_source=self.data_source_turku, parent=self.orglevel2_koserni_palvelukesk, classification_id='org:3'))
        self.orglevel3_tyollisyyspalvkesk, _ = Organization.objects.update_or_create(
            defaults=dict(name='Työllisyyspalvelukeskus'), **dict(origin_id='0720', data_source=self.data_source_turku, parent=self.orglevel2_koserni_palvelukesk, classification_id='org:3'))
        self.orglevel3_amk, _ = Organization.objects.update_or_create(
            defaults=dict(name='Ammatillinen koulutus'), **dict(origin_id='4032', data_source=self.data_source_turku, parent=self.orglevel2_sivistystoim, classification_id='org:3'))
        self.orglevel3_lukiokoul, _ = Organization.objects.update_or_create(
            defaults=dict(name='Lukiokoulutus'), **dict(origin_id='4031', data_source=self.data_source_turku, parent=self.orglevel2_sivistystoim, classification_id='org:3'))
        self.orglevel3_kirjastopalv, _ = Organization.objects.update_or_create(
            defaults=dict(name='Kirjastopalvelut'), **dict(origin_id='4453', data_source=self.data_source_turku, parent=self.orglevel2_vapaa_aikatoim, classification_id='org:3'))
        self.orglevel3_liikuntapalv, _ = Organization.objects.update_or_create(
            defaults=dict(name='Liikuntapalvelut'), **dict(origin_id='4470', data_source=self.data_source_turku, parent=self.orglevel2_vapaa_aikatoim, classification_id='org:3'))
        self.orglevel3_museopalv, _ = Organization.objects.update_or_create(
            defaults=dict(name='Museopalvelut'), **dict(origin_id='4462', data_source=self.data_source_turku, parent=self.orglevel2_vapaa_aikatoim, classification_id='org:3'))
        self.orglevel3_nuorisopalv, _ = Organization.objects.update_or_create(
            defaults=dict(name='Nuorisopalvelut'), **dict(origin_id='4480', data_source=self.data_source_turku, parent=self.orglevel2_vapaa_aikatoim, classification_id='org:3'))
        self.orglevel3_turunkaupunginork, _ = Organization.objects.update_or_create(
            defaults=dict(name='Turun Kaupunginorkesteri'), **dict(origin_id='4431', data_source=self.data_source_turku, parent=self.orglevel2_vapaa_aikatoim, classification_id='org:3'))

        # Place
        self.place_org_virtual, _ = Place.objects.update_or_create(
            defaults=dict(data_source=self.data_source_virtual, publisher=self.organization_yksityis, name='Virtuaalitapahtuma', name_fi='Virtuaalitapahtuma',
                          name_sv='Virtuell evenemang', name_en='Virtual event', description='Toistaiseksi kaikki virtuaalitapahtumat merkitään tähän paikkatietoon.'),
            **dict(id='virtual:public', origin_id='public', data_source=self.data_source_virtual))
