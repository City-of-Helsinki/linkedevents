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
        'tsl:p1': {'fi': 'Ajanvietepelit', 'sv': 'Underhållningsspel', 'en': 'Recreational games'},
        'tsl:p2': {'fi': 'Eläimet', 'sv': 'Djur', 'en': 'Animals'},
        'tsl:p3': {'fi': 'Kielet', 'sv': 'Språk', 'en': 'Languages'},
        'tsl:p4': {'fi': 'Kirjallisuus ja sanataide', 'sv': 'Litteratur och ordkonst', 'en': 'Literature and word art'},
        'tsl:p5': {'fi': 'Kuvataide ja media', 'sv': 'Bildkonst och media', 'en': 'Visual arts and media'},
        'tsl:p6': {'fi': 'Kädentaidot', 'sv': 'Hantverksskicklighet', 'en': 'Craftsmanship'},
        'tsl:p7': {'fi': 'Liikunta ja urheilu', 'sv': 'Motion och sport', 'en': 'Exercise and sports'},
        'tsl:p8': {'fi': 'Luonto', 'sv': 'Natur', 'en': 'Nature'},
        'tsl:p9': {'fi': 'Musiikki', 'sv': 'Musik', 'en': 'Music'},
        'tsl:p10': {'fi': 'Ruoka ja juoma', 'sv': 'Mat och dryck', 'en': 'Food and beverage'},
        'tsl:p11': {'fi': 'Teatteri, performanssi ja sirkus', 'sv': 'Teater, performans och cirkus', 'en': 'Theater, performance and circus'},
        'tsl:p12': {'fi': 'Tiede ja tekniikka', 'sv': 'Vetenskap och teknologi', 'en': 'Science and technology'},
        'tsl:p13': {'fi': 'Yhteisöllisyys ja auttaminen', 'sv': 'Kommunalitet och hjälpandet', 'en': 'Communality and assistance'},
        'tsl:p14': {'fi': 'Muut', 'sv': 'Övriga', 'en': 'Other'},  # Shared.
        'tsl:p15': {'fi': 'Maahanmuuttaneet', 'sv': 'Immigrerade', 'en': 'Immigrated'},
        'tsl:p16': {'fi': 'Toimintarajoitteiset', 'sv': 'Funktionshindrade', 'en': 'Functional limitations'},
        'tsl:p17': {'fi': 'Vauvat ja taaperot', 'sv': 'Spädbarn och småbarn', 'en': 'Babies and toddlers'},
        'tsl:p18': {'fi': 'Lapset ja lapsiperheet', 'sv': 'Barn och barnfamiljer', 'en': 'Children and families with children'},
        'tsl:p19': {'fi': 'Nuoret', 'sv': 'Ungdomar', 'en': 'Adolescents'},
        'tsl:p20': {'fi': 'Nuoret aikuiset', 'sv': 'Unga vuxna', 'en': 'Young adults'},
        'tsl:p21': {'fi': 'Aikuiset', 'sv': 'Vuxna', 'en': 'Adults'},
        'tsl:p22': {'fi': 'Ikääntyneet', 'sv': 'Äldre', 'en': 'Elderly'},
        'tsl:p23': {'fi': 'Opiskelijat', 'sv': 'Studenter', 'en': 'Students'},
        'tsl:p24': {'fi': 'Matkailijat', 'sv': 'Resenärer', 'en': 'Travelers'},
        'tsl:p25': {'fi': 'Työnhakijat', 'sv': 'Arbetssökande', 'en': 'Job seekers'},
        'tsl:p26': {'fi': 'Yrittäjät', 'sv': 'Företagare', 'en': 'Entrepreneurs'},
        'tsl:p27': {'fi': 'Harrastajat', 'sv': 'Hobbyister', 'en': 'Hobbyists'},
        'tsl:p28': {'fi': 'Kuvataide', 'sv': 'Bildkonst', 'en': 'Visual art'},
        'tsl:p29': {'fi': 'Tanssi', 'sv': 'Dans', 'en': 'Dancing'},
        'tsl:p30': {'fi': 'Elokuva', 'sv': 'Film', 'en': 'Movie'},
        'tsl:p31': {'fi': 'Käsityöt', 'sv': 'Hantverk', 'en': 'Handicraft'},
        'tsl:p32': {'fi': 'Terveys ja hyvinvointi', 'sv': 'Hälsa och välbefinnande', 'en': 'Health and welfare'},
        'tsl:p33': {'fi': 'Luonto ja kulttuuriympäristö', 'sv': 'Natur och kulturmiljö', 'en': 'Nature and cultural environment'},
        'tsl:p34': {'fi': 'Uskonto ja hengellisyys', 'sv': 'Religion och andlighet', 'en': 'Religion and spirituality'},
        'tsl:p35': {'fi': 'Yritystoiminta ja työelämä', 'sv': 'Företagsverksamhet och arbetsliv', 'en': 'Business and worklife'},
        'tsl:p36': {'fi': 'Yhteiskunta', 'sv': 'Samhället', 'en': 'Society'},
        'tsl:p37': {'fi': 'Historia', 'sv': 'Historia', 'en': 'History'},
        'tsl:p38': {'fi': 'Festivaalit', 'sv': 'Festivaler', 'en': 'Festivals'},
        'tsl:p39': {'fi': 'Kaupunkitapahtumat', 'sv': 'Stadsevenemang', 'en': 'City events'},
        'tsl:p40': {'fi': 'Keskustelutilaisuudet', 'sv': 'Diskussionshändelser', 'en': 'Discussion events'},
        'tsl:p41': {'fi': 'Kilpailut', 'sv': 'Tävlingar', 'en': 'Competitions'},
        'tsl:p42': {'fi': 'Kokoukset, seminaarit ja kongressit', 'sv': 'Möten, seminarier och kongresser', 'en': 'Meetings, seminars and congresses'},
        'tsl:p43': {'fi': 'Konsertit', 'sv': 'Konserter', 'en': 'Concerts'},
        'tsl:p44': {'fi': 'Koulutustapahtumat', 'sv': 'Utbildningsevenemang', 'en': 'Educational events'},
        'tsl:p45': {'fi': 'Leirit', 'sv': 'Läger', 'en': 'Camps'},
        'tsl:p46': {'fi': 'Luennot', 'sv': '', 'en': ''},
        'tsl:p47': {'fi': 'Markkinat', 'sv': '', 'en': ''},
        'tsl:p48': {'fi': 'Messut', 'sv': '', 'en': ''},
        'tsl:p49': {'fi': 'Myyjäiset', 'sv': '', 'en': ''},
        'tsl:p50': {'fi': 'Näyttelyt', 'sv': '', 'en': ''},
        'tsl:p51': {'fi': 'Opastukset', 'sv': '', 'en': ''},
        'tsl:p52': {'fi': 'Retket', 'sv': '', 'en': ''},
        'tsl:p53': {'fi': 'Työpajat', 'sv': 'Verkstad', 'en': 'Workshop'},
        'tsl:p54': {'fi': 'Verkostoitumistapahtumat', 'sv': '', 'en': ''},
        'tsl:p55': {'fi': 'Muu', 'sv': '', 'en': ''},
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
