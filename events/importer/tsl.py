# -*- coding: utf-8 -*-

# Dependencies.

# Logging:
import time
import logging
from os import mkdir
from os.path import abspath, join, dirname, exists, basename, splitext

# Django:
from django_orghierarchy.models import Organization
from django_orghierarchy.models import OrganizationClass
from events.models import DataSource, BaseModel, Keyword

# Importer specific:
from .base import Importer, register_importer

# Type checking:
from typing import Any

# Setup Logging:
if not exists(join(dirname(__file__), 'logs')):
    mkdir(join(dirname(__file__), 'logs'))

logger = logging.getLogger(__name__)  # Per module logger
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


def tsl() -> dict:
    '''
    These are custom with multilang support.
    Prefix & ID are hardcoded as visual cues for mapping the management commands.
    '''
    data = {
        'tsl:p1': {'fi': 'Ajanvietepelit', 'sv': 'Fritidsspel', 'en': 'Recreational games'},
        'tsl:p2': {'fi': 'Eläimet', 'sv': 'Djur', 'en': 'Animals'},
        'tsl:p3': {'fi': 'Kielet', 'sv': 'Språk', 'en': 'Languages'},
        'tsl:p4': {'fi': 'Kirjallisuus ja sanataide', 'sv': 'Litteratur och ordkonst', 'en': 'Literature and literary art'},
        'tsl:p5': {'fi': 'Kuvataide ja media', 'sv': 'Bildkonst och media', 'en': 'Fine arts and media'},
        'tsl:p6': {'fi': 'Kädentaidot', 'sv': 'Hantverk', 'en': 'Handicrafts'},
        'tsl:p7': {'fi': 'Liikunta ja urheilu', 'sv': 'Motion och idrott', 'en': 'Physical exercise and sports'},
        'tsl:p8': {'fi': 'Luonto', 'sv': 'Naturen', 'en': 'Nature'},
        'tsl:p9': {'fi': 'Musiikki', 'sv': 'Musik', 'en': 'Music'},
        'tsl:p10': {'fi': 'Ruoka ja juoma', 'sv': 'Mat och drycker', 'en': 'Food and beverages'},
        'tsl:p11': {'fi': 'Teatteri, performanssi ja sirkus', 'sv': 'Teaterkonst, performance och cirkus', 'en': 'Theatre, performance and circus'},
        'tsl:p12': {'fi': 'Tiede ja tekniikka', 'sv': 'Vetenskap och teknik', 'en': 'Science and technology'},
        'tsl:p13': {'fi': 'Yhteisöllisyys ja auttaminen', 'sv': 'Sammanhållning och hjälp', 'en': 'Communality and helping'},
        # 'tsl:p14': {'fi': 'Muut', 'sv': 'Övriga', 'en': 'Other'},  # Shared. # EI OLE! REPLACED BY: TSL:P55
        'tsl:p15': {'fi': 'Maahanmuuttaneet', 'sv': 'Invandrare', 'en': 'Immigrants'},
        'tsl:p16': {'fi': 'Toimintarajoitteiset', 'sv': 'Personer med funktionsbegränsning', 'en': 'Disabled persons'},
        'tsl:p17': {'fi': 'Vauvat ja taaperot', 'sv': 'Babyer och barn i småbarnsåldern', 'en': 'Babies and toddlers'},
        'tsl:p18': {'fi': 'Lapset ja lapsiperheet', 'sv': 'Barn och barnfamiljer', 'en': 'Children and families with children'},
        'tsl:p19': {'fi': 'Nuoret', 'sv': 'Ungdomar', 'en': 'Young people'},
        'tsl:p20': {'fi': 'Nuoret aikuiset', 'sv': 'Unga vuxna', 'en': 'Young adults'},
        'tsl:p21': {'fi': 'Aikuiset', 'sv': 'Vuxna', 'en': 'Adults'},
        'tsl:p22': {'fi': 'Ikääntyneet', 'sv': 'Äldre', 'en': 'Older adults'},
        'tsl:p23': {'fi': 'Opiskelijat', 'sv': 'Studerande', 'en': 'Students'},
        # 'tsl:p24': {'fi': 'Matkailijat', 'sv': 'Resenärer', 'en': 'Travelers'}, # EI OLE OLEMASSA, REPLACED BY: NUORET AIKUISET P20
        'tsl:p25': {'fi': 'Työnhakijat', 'sv': 'Arbetssökande', 'en': 'Jobseekers'},
        'tsl:p26': {'fi': 'Yrittäjät', 'sv': 'Företagare', 'en': 'Entrepreneurs'},
        # 'tsl:p27': {'fi': 'Harrastajat', 'sv': 'Hobbyister', 'en': 'Hobbyists'}, # EI OLE OLEMASSA, EI OLE REPLACEMENT
        'tsl:p28': {'fi': 'Kuvataide', 'sv': 'Bildkonst', 'en': 'Visual arts'},
        'tsl:p29': {'fi': 'Tanssi', 'sv': 'Dans', 'en': 'Dance'},
        'tsl:p30': {'fi': 'Elokuva', 'sv': 'Filmkonst', 'en': 'Cinema'},
        'tsl:p31': {'fi': 'Käsityöt', 'sv': 'Handarbeten och hantverk', 'en': 'Handicrafts'},
        'tsl:p32': {'fi': 'Terveys ja hyvinvointi', 'sv': 'Hälsa och välbefinnande', 'en': 'Health and well-being'},
        'tsl:p33': {'fi': 'Luonto ja kulttuuriympäristö', 'sv': 'Naturen och kulturmiljö', 'en': 'Nature and cultural environment'},
        'tsl:p34': {'fi': 'Uskonto ja hengellisyys', 'sv': 'Religion och andlighet', 'en': 'Religion and religious spirituality'},
        'tsl:p35': {'fi': 'Yritystoiminta ja työelämä', 'sv': 'Företagsverksamhet och arbetsliv', 'en': 'Business operations and working life'},
        'tsl:p36': {'fi': 'Yhteiskunta', 'sv': 'Samhället', 'en': 'Society'},
        'tsl:p37': {'fi': 'Historia', 'sv': 'Historia', 'en': 'History'},
        'tsl:p38': {'fi': 'Festivaalit', 'sv': 'Festivaler', 'en': 'Festivals'},
        'tsl:p39': {'fi': 'Kaupunkitapahtumat', 'sv': 'Stadsevenemang', 'en': 'Urban events'},
        'tsl:p40': {'fi': 'Keskustelutilaisuudet', 'sv': 'Diskussionsevenemang', 'en': 'Discussions'},
        'tsl:p41': {'fi': 'Kilpailut', 'sv': 'Tävlingar', 'en': 'Competitions'},
        'tsl:p42': {'fi': 'Kokoukset, seminaarit ja kongressit', 'sv': 'Möten, seminarier och konferenser', 'en': 'Meetings, seminars and conferences'},
        'tsl:p43': {'fi': 'Konsertit', 'sv': 'Konserter', 'en': 'Concerts'},
        'tsl:p44': {'fi': 'Koulutustapahtumat', 'sv': 'Utbildningsevenemang', 'en': 'Educational events'},
        'tsl:p45': {'fi': 'Leirit', 'sv': 'Läger', 'en': 'Camps'},
        'tsl:p46': {'fi': 'Luennot', 'sv': 'Föreläsningar', 'en': 'Lectures'},
        'tsl:p47': {'fi': 'Markkinat', 'sv': 'Marknader', 'en': 'Fairs and markets'},
        'tsl:p48': {'fi': 'Messut', 'sv': 'Mässor', 'en': 'Trade fairs'},
        'tsl:p49': {'fi': 'Myyjäiset', 'sv': 'Försäljningar', 'en': 'Jumble sales'},
        'tsl:p50': {'fi': 'Näyttelyt', 'sv': 'Utställningar', 'en': 'Exhibitions'},
        'tsl:p51': {'fi': 'Opastukset', 'sv': 'Guidade turer', 'en': 'Guided tours'},
        'tsl:p52': {'fi': 'Retket', 'sv': 'Utfärder', 'en': 'Trips'},
        'tsl:p53': {'fi': 'Työpajat', 'sv': 'Verkstäder', 'en': 'Workshops'},
        'tsl:p54': {'fi': 'Verkostoitumistapahtumat', 'sv': 'Nätverksevenemang', 'en': 'Networking events'},
        'tsl:p55': {'fi': 'Muu sisältö', 'sv': 'Övrigt innehåll', 'en': 'Other content'},
        'tsl:p56': {'fi': 'Teatteri, tanssi ja sirkus', 'sv': 'Teaterkonst, dans och cirkus', 'en': 'Theatre, dance and circus'},
        'tsl:p57': {'fi': 'Muu tapahtumatyyppi', 'sv': 'Övrig evenemangstyp', 'en': 'Other event type'},
        'tsl:p58': {'fi': 'Muu', 'sv': 'Övrig', 'en': 'Other'},
        'tsl:p59': {'fi': 'Kädentaidot', 'sv': 'Hantverk', 'en': 'Handicrafts'},
        'tsl:p60': {'fi': 'Liikunta', 'sv': 'Motion', 'en': 'Physical exercise'},
        'tsl:p61': {'fi': 'Kielet ja kirjallisuus', 'sv': 'Språk och litteratur', 'en': 'Languages and literature'},
        'tsl:p62': {'fi': 'Viestintä ja media', 'sv': 'Kommunikation och media', 'en': 'Communication and media'},
        'tsl:p63': {'fi': 'Historia, yhteiskunta ja talous', 'sv': 'Historia, samhälle och ekonomi', 'en': 'History, society and economy'},
        'tsl:p64': {'fi': 'Psykologia ja filosofia', 'sv': 'Psykologi och filosofi', 'en': 'Psychology and philosophy'},
        'tsl:p65': {'fi': 'Kasvien hoito ja viljely', 'sv': 'Växtskötsel och odling', 'en': 'Plant care and cultivation'},
        'tsl:p66': {'fi': 'Luonto ja ympäristö', 'sv': 'Natur och miljö', 'en': 'Nature and environment'},
        'tsl:p67': {'fi': 'Tietotekniikka', 'sv': 'Informationsteknik', 'en': 'Information technology'},
        'tsl:p68': {'fi': 'Muu koulutus', 'sv': 'Övrig utbildning', 'en': 'Other education'},
    }
    return data


@register_importer
class TslImporter(Importer):
    # Importer class dependant attributes:
    name = "tsl"  # Command calling name.
    supported_languages = ['fi', 'sv', 'en']  # Base file requirement.

    def iterator(self: 'events.importer.tsl.TslImporter', data: dict, key: str, query: Any, obj_model: tuple, attr_map: tuple) -> None:
        ''' Main class data logic. Create DB objects & set class attributes.
            This was created with easy expandability of the setup data dictionary in mind.
            We are using save() throughout this program to avoid race conditions with update_or_create()
            '''
        for idx, sub_key in enumerate(data[key]):
            try:
                q_obj = query()
                for count, attr in enumerate(obj_model):
                    setattr(q_obj, attr, data[key][sub_key][count])
                q_obj.save()
                setattr(self, attr_map[idx], query.objects.get(
                    id=data[key][sub_key][0]))
                keyfinder = '%s_%s' % (key, sub_key)
                for t_key in data['funcargs']['terms']:
                    for sub_t_key in data[t_key]:
                        if data[t_key][sub_t_key][-1] == keyfinder:
                            data[t_key][sub_t_key][-1] = getattr(
                                self, attr_map[idx])
            except Exception as e:
                logger.error(e)

    def save_kw(self: 'events.importer.tsl.TslImporter') -> None:
        try:
            for k, v in self.keywords.items():
                kw = Keyword(data_source=getattr(self, 'data_source'))
                kw.id = k
                kw.publisher = getattr(self, 'organization')
                for lang, lang_val in v.items():
                    langformat = 'name_%s' % lang
                    setattr(kw, langformat, lang_val)
                kw.created_time = BaseModel.now()
                kw.save()
                logger.info("Saved TSL keyword ID: %s" % k)
        except Exception as e:
            logger.error(e)
            pass

    def setup(self: 'events.importer.tsl.TslImporter') -> None:
        ''' 
            This can be used as a template for other importers as it's constructed
            to be very easily expandable. It also avoids race condition issues by utiling save().

            To add a new model we just define it as a key, add the attribute name to attr_maps,
            add the model values to model_maps and add the required values mapped by those
            model_maps within. Remember that the values that are underneath each other
            are creater later than the former so you'd want to follow this mindset throughout the data dict.

            This might look like a static assignment importer but
            we use the magic of setattr to create the necessary objects before assignment.

            Typically we define data_sources to organisations after they have been created,
            but here we don't even have to worry about long update_or_create chains or get chains
            should our data be large. If you take a look at "org", the data_source is defined as
            'ds' followed by '_tsl'. The importer by itself finds the correct data_source when it is
            trying to create the organization 'tsl'.
        '''
        self.data = {
            # TSL and the Public DataSource for Organizations model.
            'ds': {
                'tsl': ('tsl', 'Turun sanalista', True),
                'org': ('org', 'Ulkoa tuodut organisaatiotiedot', True),
            },
            # Public organization class for all instances.
            'orgclass': {
                'sanasto': ['org:13', '13', 'Sanasto', BaseModel.now(), 'ds_org'],
            },
            # TSL organization.
            'org': {
                'tsl': ['tsl:3000', '3000', 'TSL', BaseModel.now(), 'org:13', 'ds_tsl'],
            },
            # Attribute name mapping for all due to class related attributes (ex. data_source and organization are necessary).
            'attr_maps': {
                'ds': ('data_source', 'data_source_org'),
                # Tuples get converted to strings for single values if they don't contain , at the end
                'orgclass': ('organization_class_13',),
                'org': ('organization',),
            },
            # Models for easy iteration (Selected attributes):
            'model_maps': {
                'ds': ('id', 'name', 'user_editable'),
                'orgclass': ('id', 'origin_id', 'name', 'created_time', 'data_source_id'),
                'org': ('id', 'origin_id', 'name', 'created_time', 'classification_id', 'data_source_id'),
            },
            # Function arguments.
            'funcargs': {
                'terms': ('ds', 'orgclass', 'org'),
                'termobjs': (DataSource, OrganizationClass, Organization)
            },
        }
        # Keys in data share per element relevant information. Bring together element per key in data dict for iterator params.
        mapped = list(map(lambda f, fto, mm, atm: [f, fto, self.data['model_maps'][mm], self.data['attr_maps'][atm]],
                      self.data['funcargs']['terms'], self.data['funcargs']['termobjs'], self.data['model_maps'], self.data['attr_maps']))
        # Call the iterator function. Params use the mapped elements.
        for args in mapped:
            self.iterator(
                data=self.data, key=args[0], query=args[1], obj_model=args[2], attr_map=args[3])
        logger.info("Setup finished...")
        self.handle()

    def handle(self: 'events.importer.tsl.TslImporter') -> None:
        logger.info("Gather TSL keywords...")
        self.keywords = tsl()
        logger.info("Saving TSL keywords...")
        self.save_kw()
        logger.info("Importer finished in: %s" % time.process_time())
