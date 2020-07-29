import logging
import requests
import requests_cache
import re 
import dateutil.parser
import time
import pytz
import bleach


from datetime import datetime, timedelta
from django.utils.html import strip_tags 
from events.models import Event, Keyword, DataSource, Place, License, Image, Language
from django_orghierarchy.models import Organization, OrganizationClass
from pytz import timezone
from django.conf import settings

from .util import clean_text
from .sync import ModelSyncher
from .base import Importer, register_importer, recur_dict
from .yso import KEYWORDS_TO_ADD_TO_AUDIENCE

#Run comand: python manage.py event_import tku_old_events --events
print('Run comand: python manage.py event_import tku_old_events --events')

# Per module logger
logger = logging.getLogger(__name__)
#Setting the threshold of logger to DEBUG 
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('info.log')
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)



#Setting the threshold of logger to DEBUG 


LOCATIONS = {
    # Library name in Finnish -> ((library node ids in event feed), tprek id)
    #u"Arabianrannan kirjasto": ((10784, 11271), 8254),
}
# "Etätapahtumat" are mapped to our new fancy "Tapahtuma vain internetissä." location
#INTERNET_LOCATION_ID = settings.SYSTEM_DATA_SOURCE_ID + ':internet'
#However, Tku importer utilizes virtual:public

VIRTUAL_LOCATION_ID = "virtual:public"

#This is our drupal JSON page, it currently lists 250 events. Our logic dictates
#that we must get the main events first, and based on them import all the child events and rest
#according to our mapping with database connectivity; read and write.
#Please note "json_beta" which was specifically intended for our use.
TKUDRUPAL_BASE_URL = 'https://kalenteri.turku.fi/admin/event-exports/json_beta'

KEYWORD_LIST = []

#These are our main Turku Linkedevents "Topics" YSO keywords list.
#Essentially, what this means is, we have different tags to indicate the type of
#event this is. Is our event a Music related event, is it a Museum event,
#a conference event, etc?
TURKU_KEYWORD_IDS = {
    'Festivaalit': 'yso:p1304',  # festivaalit
    'Konferenssit ja kokoukset': 'yso:p38203',  # konferenssit (ja kokoukset)
    'Messut': 'yso:p4892', # messut
    'Myyjäiset': 'yso:p9376',  # myyjäiset
    'Musiikki': 'yso:p1808',  # musiikki
    'Museot': 'yso:p4934',  # museot
    'Näyttelyt': 'yso:p5121',  # näyttelyt
    'Luennot': 'yso:p15875', # luennot
    'Osallisuus': 'yso:p5164',  # osallisuus
    'Monikulttuurisuus': 'yso:p10647',  # monikulttuurisuus
    'Retket': 'yso:p25261', # retket
    'Risteilyt': 'yso:p1917', # risteilyt
    'Matkat': 'yso:p366',  # matkat
    'Matkailu': 'yso:p3917', # matkailu
    'Opastus': 'yso:p2149',  # opastus
    'Teatteritaide': 'yso:p2625', # teatteritaide
    'Muu esittävä taide': 'yso:p2850', # muu esittävä taide
    'Urheilu': 'yso:p965', # urheilu
    'Kirjallisuus': 'yso:p8113', # kirjallisuus
    'Tapahtumat ja toiminnat': 'yso:p15238', # tapahtumat ja toiminnat
    'Ruoka': 'yso:p3670',  # ruoka
    'Tanssi': 'yso:p1278',  # tanssi
    'Työpajat': 'yso:p19245',  # työpajat
    'Ulkoilu': 'yso:p2771',  # ulkoilu
    'Etäosallistuminen': 'yso:p26626', #etäosallistuminen
}
#This is Turku YSO based "Audience" keyword list.
#This essentially means to whom the event applies to. Is it for example directed towards:
#the young, adults, child families etc?
TURKU_AUDIENCES_KEYWORD_IDS = {
    'Aikuiset': 'yso:p5590', #-> Aikuiset
    'Lapsiperheet': 'yso:p13050', #-> Lapsiperheet
    'Maahanmuttajat': 'yso:p6165', #-> Maahanmuuttujat
    'Matkailijat': 'yso:p16596', #-> Matkailijat
    'Nuoret': 'yso:p11617', #-> Nuoret
    'Seniorit': 'yso:p2433', #-> Seniorit
    'Työnhakijat': 'yso:p9607', #-> Työnhakijat
    'Vammaiset': 'yso:p7179', #-> Vammaiset
    'Vauvat': 'yso:p15937', #-> Vauvat
    'Viranomaiset': 'yso:p6946', #-> Viranomaiset
    'Järjestöt': 'yso:p1393', #-> järjestöt  
    'Yrittäjät': 'yso:p1178', #-> Yrittäjät  
}

#Where our Drupal YSO category is linked to in our Turku version.
TURKU_DRUPAL_EVENTS_EN_YSOID = {   
    'Exhibits': 'yso:p5121', #utställningar #Näyttelyt 
    'Festival and major events': 'yso:p1304',	# festivaler #Festivaalit ja suurtapahtumat (http://www.yso.fi/onto/yso/p1304)
	'Meetings and congress ': 'yso:p7500',#möten, symposier (sv), kongresser (sv), sammanträden (sv) #Kokoukset (http://www.yso.fi/onto/yso/p38203)
	'Trade fair and fair': 'yso:p4892', #Messut ,mässor (evenemang), (messut: http://www.yso.fi/onto/yso/p4892; myyjäiset : http://www.yso.fi/onto/yso/p9376)
    'Music': 'yso:p1808',#Musiikki, musik, http://www.yso.fi/onto/yso/p1808
	'Museum': 'yso:p4934',#Museo,  museum (en), museer (sv) (yso museot: http://www.yso.fi/onto/yso/p4934)
	'Lectures':'yso:p15875',#Luennot,föreläsningar (sv), http://www.yso.fi/onto/yso/p15875
	'Participation':'yso:p5164',#Osallisuus,delaktighet (sv), http://www.yso.fi/onto/yso/p5164
	'Multiculturalism':'yso:p10647',#Monikulttuurisuus,multikulturalism, http://www.yso.fi/onto/yso/p10647
	'Trips,cruises and tours':'yso:p3917',#Matkailu, turism (sv)
    'Guided tours and sightseeing tours':'yso:p2149',#guidning (sv),Opastukset: http://www.yso.fi/onto/yso/p2149; 
    'Theatre and other performance art':'yso:p2850',#scenkonst (sv),Esittävä taide: http://www.yso.fi/onto/yso/p2850;  
	'Sports':'yso:p965',#Urheilu,idrott, http://www.yso.fi/onto/yso/p965
	'Christmas':'yso:p419',#Joulu,julen, http://www.yso.fi/onto/yso/p419	
	'Literature':'yso:p8113', #Kirjallisuus, litteratur (sv), http://www.yso.fi/onto/yso/p8113
    'Others':'yso:10727', #Ulkopelit,(-ei ysoa, ei kategoriaa)	
}
#Where our Drupal YSO audience category is linked to in our Turku version.
TURKU_DRUPAL_AUDIENCES_KEYWORD_EN_YSOID = {
    'Adults': 'yso:p5590', 
    'Child families': 'yso:p13050', 
    'Immigrants': 'yso:p6165', 
    'Travellers': 'yso:p16596', 
    'Youth': 'yso:p11617', 
    'Elderly': 'yso:p2433', 
    'Jobseekers': 'yso:p9607', 
    'Disabled': 'yso:p7179', 
    'Infants and toddlers': 'yso:p15937', 
    'Authorities': 'yso:p6946', 
    'Associations and communities': 'yso:p1393',
    'Entrepreneurs': 'yso:p1178', 
}

#Our only 3 languages.
LANGUAGES_TURKU_OLD =  ['fi', 'sv' , 'en']


CITY_LIST = ['turku',]# ['turku', 'kaarina', 'lieto', 'raisio']

#Our timezone for database.
LOCAL_TZ = timezone('Europe/Helsinki')

#mark_deleted and check_deleted are the systems for deleted events.
#We need this in our import, if our id has been deleted from the linkedevents side, we don't
#want to re-import the specific event into our database.
def mark_deleted(obj):
    if obj.deleted:
        return False
    obj.deleted = True
    obj.save(update_fields=['deleted'])
    return True

def check_deleted(obj):
    # We don't want to delete past events, so as far as the importer cares, they are considered deleted
    if obj.deleted or obj.end_time < datetime.now(pytz.utc):
        return True
    return False

class APIBrokenError(Exception):
    pass

@register_importer
class TurkuOriginalImporter(Importer):
    name = "tku_old_events"
    supported_languages = ['fi', 'sv', 'en'] #LANGUAGES
    languages_to_detect = []
    current_tick_index = 0
    kwcache = {}
    

    def setup(self):
        self.languages_to_detect = [lang[0].replace('-', '_') for lang in settings.LANGUAGES
                                    if lang[0] not in self.supported_languages]
         #Turku spesific datasources
        ds_args = dict(id='turku')
        defaults = dict(name='Kuntakohtainen data Turun Kaupunki')
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args)
        self.tpr_data_source = DataSource.objects.get(id='tpr')
        self.org_data_source = DataSource.objects.get(id='org')
        self.system_data_source = DataSource.objects.get(id=settings.SYSTEM_DATA_SOURCE_ID)

        #Public organizations class for all instances
        ds_args = dict(origin_id='3', data_source=self.org_data_source)
        defaults = dict(name='Kunta')
        self.organizationclass, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)

        org_args = dict(origin_id='853', data_source=self.org_data_source, classification_id="org:3")
        defaults = dict(name='Turku')
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

        #Virtual events data source 
        ds_args4 = dict(id='virtual', user_editable=True)
        defaults4 = dict(name='Virtuaalitapahtumat (ei paikkaa, vain URL)')
        self.data_source_virtual, _ = DataSource.objects.get_or_create(defaults=defaults4, **ds_args4)
        
        #Virtual events public organisations
        org_args4 = dict(origin_id='3000', data_source=self.data_source_virtual, classification_id="org:14")
        defaults4 = dict(name='Virtuaalitapahtumat')        
        self.organization_virtual, _ = Organization.objects.get_or_create(defaults=defaults4, **org_args4)

        #Create virtual events location if not already made
        defaults5 = dict(data_source=self.data_source_virtual,
                        publisher=self.organization_virtual,
                        name='Virtuaalitapahtuma',
                        name_fi='Virtuaalitapahtuma',
                        name_sv='Virtuell evenemang',
                        name_en='Virtual event',
                        description='Toistaiseksi kaikki virtuaalitapahtumat merkitään tähän paikkatietoon.',)
        self.internet_location, _ = Place.objects.get_or_create(id=VIRTUAL_LOCATION_ID, defaults=defaults5)
        
        try:
            self.event_only_license = License.objects.get(id='event_only')
        except License.DoesNotExist:
            self.event_only_license = None

        try:
            self.cc_by_license = License.objects.get(id='cc_by')
        except License.DoesNotExist:
            self.cc_by_license = None    


        #Here we compare inner Linkedevents YSO keywords in events_keyword (Keyword) list.
        try:
            yso_data_source = DataSource.objects.get(id='yso')
        except DataSource.DoesNotExist:
            yso_data_source = None

        if yso_data_source:
            # Build a cached list of YSO keywords
            cat_id_set = set()
            for yso_val in TURKU_KEYWORD_IDS.values():
                if isinstance(yso_val, tuple):
                    for t_v in yso_val:
                        cat_id_set.add(t_v)
                else:
                    cat_id_set.add(yso_val)

            KEYWORD_LIST = Keyword.objects.filter(data_source=yso_data_source).\
                filter(id__in=cat_id_set)
            self.yso_by_id = {p.id: p for p in KEYWORD_LIST}
        else:
            self.yso_by_id = {}

        if self.options['cached']:
            requests_cache.install_cache('turku')
            self.cache = requests_cache.get_cache()
        else:
            self.cache = None
    
    #This reads our JSON dump and fills the eventTku with our data
    @staticmethod
    def _get_eventTku(event_el):        
        eventTku = recur_dict()
        eventTku = event_el
         
        return eventTku


    def _cache_super_event_id(self, sourceEventSuperId):
        #This gets our specific superid from the Event table in our DataSource.

        #Linked Events event id type is source:origin_id like turku:234234
        superid = (self.data_source.name + ':' + sourceEventSuperId)
        one_super_event = Event.objects.get(id=superid)
        return one_super_event

    
    def dt_parse(self, dt_str):
        """Convert a string to UTC datetime"""
        # Times are in UTC+02:00 timezone
        return LOCAL_TZ.localize(
                dateutil.parser.parse(dt_str),
                is_dst=None).astimezone(pytz.utc)
   

    def timeToTimestamp(self, origTime):

        timestamp = time.mktime(time.strptime(origTime, '%d.%m.%Y %H.%M'))
        
        dt_object = datetime.fromtimestamp(timestamp)

        return str(dt_object)


    def _import_child_event(self, lang, eventTku):
             
        event_Mother = None
        event_Recurring = None

        #Linked Events event id type is source:origin_id like turku:234234
        sourceEventSuperId = eventTku['drupal_nid_super']
        sourceEventId = eventTku['drupal_nid']
        superId= (self.data_source.id + ':' + sourceEventSuperId)
        sourceId = (self.data_source.id + ':' + sourceEventId)      
      
        try:
            event_Mother = Event.objects.get(id=superId)
        except:
            logger.info('No motherevent found for child event who finds  its own super event No.' + superId)
            return
        try:
            event_Recurring = Event.objects.get(super_event_id = event_Mother.id, super_event_type = Event.SuperEventType.RECURRING)
        except:
            logger.info('No mother events  for child are found super_event_id')

        if event_Recurring:    
            event_Mother = event_Recurring

        usableSuperEventId = event_Mother.id
            
        if not event_Mother.deleted:
            
        
            #If the mother event's type is "umbrella", we create a new child with the type of "recurring" including the same id as the mother event has, 
            # and connect it to this mother event with a reference key. 
            # After that, all original children are found linked to this 'recurring' event because for now on, they are found only
            #as this mother event's children and therefore, they are also the original mother event's grandchildren.
           
            #create a new umbrella with new id and change old mother super_event_type to recurring

            #event_type 'umbrella' is level 1 event, 'recurring' is level 2 event and null is level 3 event (serie)
            if event_Mother.super_event_type == Event.SuperEventType.UMBRELLA:
         
                event_Mother1 = event_Mother
                
                

                event_Mother1.id = event_Mother.id + 's'
                event_Mother1.super_event_type = Event.SuperEventType.RECURRING
                event_Mother1.start_time = self.dt_parse(self.timeToTimestamp(str(eventTku['start_date'])))
                event_Mother1.end_time = self.dt_parse(self.timeToTimestamp(str(eventTku['end_date'])))
                event_Mother1.super_event_id = usableSuperEventId

                orig_id = str(event_Mother1.id)

                orig_id = orig_id.split(':')

                oid = orig_id[1]

                event_Mother1.origin_id = oid                   
     
                
                event_Mother1.save(force_insert=True)
               
            
             #update old mother from umbrella to recurring type, set a new time fields as well as set super id and save it                
               
                
                            
            elif event_Mother.super_event_type == Event.SuperEventType.RECURRING:
                #NOTE!change  mother's type to child's type from recurring to null, set a new time fields as well as set superid and save it 
             
                event_Mother2 = event_Mother

                event_Mother2.id = sourceId + 'ss'
                event_Mother2.super_event_type = None
                event_Mother2.start_time = self.dt_parse(self.timeToTimestamp(str(eventTku['start_date'])))
                event_Mother2.end_time = self.dt_parse(self.timeToTimestamp(str(eventTku['end_date'])))
                event_Mother2.super_event_id = usableSuperEventId

                orig_id = str(event_Mother2.id)

                orig_id = orig_id.split(':')

                oid = orig_id[1]

                event_Mother2.origin_id = oid      
               
                event_Mother.save()
               

    def _import_event(self, lang, event_el, events, event_image_url):
        
        
        #This calls _get_eventTku and returns our eventTku variable.
        eventTku = self._get_eventTku(event_el)
     
        #This isn't necessary since we are in Finland, but this parsing would be necessary if
        #we wanted an instance of Linkedevents in a different timezone.
        start_time = self.dt_parse(self.timeToTimestamp(str(eventTku['start_date'])))
        end_time = self.dt_parse(self.timeToTimestamp(str(eventTku['end_date'])))


        # Import only at most one year old events
        if end_time < datetime.now().replace(tzinfo=LOCAL_TZ) - timedelta(days=365):
            return {'start_time': start_time, 'end_time': end_time}
  
    
        #If is_hobby == 1, we don't take it.
        #If none, we don't import the current event.
        if "1" in eventTku['is_hobby']:
            pass
        else:
            #Our event id is defined here.
            eid = int(eventTku['drupal_nid'])

            #eventItem is constructed here, it contains our data_source and organization data.
            #This is what gets sent to our database.                
            
            eventItem = events[eid]
            eventItem['id'] = '%s:%s' % (self.data_source.id, eid)
            eventItem['origin_id'] = eid
            eventItem['data_source'] = self.data_source
            eventItem['publisher'] = self.organization
            eventItem['end_time'] = end_time

            event_categories = eventItem.get('event_categories', set())

            if event_categories:
                pass
            else:
                logger.info("No event_categories found for current event. Skipping...")

        
            ok_tags = ('u', 'b', 'h2', 'h3', 'em', 'ul', 'li', 'strong', 'br', 'p', 'a')

            eventItem['name'] = {"fi": eventTku['title_fi'], "sv": eventTku['title_sv'], "en": eventTku['title_en']}
            eventItem['description'] = {
                "fi": bleach.clean(str(eventTku['description_markup_fi']),tags=ok_tags,strip=True),
                "sv": bleach.clean(str(eventTku['description_markup_sv']),tags=ok_tags,strip=True),
                "en": bleach.clean(str(eventTku['description_markup_en']),tags=ok_tags,strip=True)
            }

            eventItem['short_description'] = {
                "fi": eventTku['lead_paragraph_markup_fi'],
                "sv": eventTku['lead_paragraph_markup_sv'],
                "en": eventTku['lead_paragraph_markup_en']
            }

            location_extra_info = str(eventTku['address_extension']) + ', ' + str(eventTku['city_district']) + ', ' + str(eventTku['place'])

            eventItem['location_extra_info'] = {
                "fi": location_extra_info,
                "sv": location_extra_info,
                "en": location_extra_info
            }
            
            
            #Because these are motherevents, so we type them as "umbrella"
            eventItem['super_event_type'] = Event.SuperEventType.UMBRELLA
            
            
            event_image_ext_url = ''
            image_license = ''
            event_image_license = self.event_only_license

           

            #NOTE! Events image is not usable in Helmet , so we must use this Lippupiste.py way to do it         
            if event_image_url != None:
                event_image_ext_url = event_image_url
                

                #event_image_license 1 or 2 (1 is 'event_only' and 2 is 'cc_by' in Linked Events) 
                if eventTku['event_image_license'] != None:
                    image_license = eventTku['event_image_license']    
                    if image_license == '1':     
                        event_image_license = self.event_only_license
                    elif image_license == '2':     
                        event_image_license = self.cc_by_license

                eventItem['images'] = [{
                    'url': event_image_ext_url,
                    'license': event_image_license,
                    }]
   
            
            def set_attr(field_name, val):
                if field_name in eventItem:
                    if eventItem[field_name] != val:
                        logger.warning('Event %s: %s mismatch (%s vs. %s)' %
                                    (eid, field_name, eventItem[field_name], val))
                        return
                eventItem[field_name] = val
            

            #if 'date_published' not in event:
                # Publication date changed based on language version, so we make sure
                # to save it only from the primary event.
            
            eventItem['date_published'] = self.dt_parse(self.timeToTimestamp(str(eventTku['start_date'])))
            
            
            set_attr('start_time', self.dt_parse(self.timeToTimestamp(str(eventTku['start_date']))))
            set_attr('end_time', self.dt_parse(self.timeToTimestamp(str(eventTku['end_date']))))
            

           # Because our Drupal json of Turku old events has not included any field to event_in_language, we set "fi" as default based on info from old Turku events
            event_keywords = eventItem.get('keywords', set())
            event_audience = eventItem.get('audience', set())
            
            event_in_language = eventItem.get('in_language', set())
            try:
                eventLang = Language.objects.get(id='fi')
            except:
                logger.info('language (fi) not found')
            
            if (eventLang):
                event_in_language.add(self.languages[eventLang.id])
           
           # Also, the current language is always included
            eventItem['in_language'] = event_in_language
            
           
            #Here we separate all new Turku main category words from Drupal category fields and add them to the keyword list 
            if eventTku['event_categories'] != None:
                for name in eventTku['event_categories']:

                    if name in TURKU_DRUPAL_EVENTS_EN_YSOID.keys():
                        ysoId = str(TURKU_DRUPAL_EVENTS_EN_YSOID[name].values())
                        #yso = TURKU_KEYWORD_IDS[name]
                        if isinstance(ysoId, tuple):

                            event_keywords.add(self.yso_by_id['yso:' + ysoId])

                        else:
                            event_audience.add(self.yso_by_id['yso:' + ysoId])        

            
            #Here we separate all new main audience words from Drupal audience fields anf add them to the keyword list
            
            if eventTku['target_audience'] != None:
                for name in eventTku['target_audience']:

                    if name in TURKU_DRUPAL_AUDIENCES_KEYWORD_EN_YSOID.keys():
                        ysoId = str(TURKU_DRUPAL_AUDIENCES_KEYWORD_EN_YSOID[name].values())
                        #yso = TURKU_KEYWORD_IDS[name]
                        if isinstance(ysoId, tuple):

                            event_keywords.add(self.yso_by_id['yso:' + ysoId])

                        else:
                            event_audience.add(self.yso_by_id['yso:' + ysoId])        


    
            # Here we get all keywords for the event from Drupal json interface, then we check if they exit in the yso dictionary and finally, we add them to the event_keywords 
            # using the command: event_keywords.add
            # Not all the replacements are valid keywords. yso has some data quality issues
            
            if eventTku['keywords'] != None:
                
                old_name = str(eventTku['keywords'])
                try:
                    old_keyword = Keyword.objects.get(old_name)

                    self.old_keys = {x.id: x for x in old_keyword}

                    for x in old_keyword:
                        event_keywords.add(self.old_keys[x.id])

                    eventItem['keywords'] = event_keywords
                    logger.info('Keywords: ' + event_keywords)

                
                except:
                    print('Warning!' + ' keywords not found:' + eventTku['keywords'])
                    logger.warning('Moderator should add the following keywords ' + eventTku['keywords'])    
                    pass    

         
                    

 
            #Here we seach events_place based on the unit number of the place in Palvelukartta-map 
            # One of the type 7 nodes (either Tapahtumat, or just the library name)
            # points to the location, which is mapped to Linked Events keyword ID
            # Online events lurk in node 7 as well
            tprNo = ''

            if eventTku['event_categories'] != None: 
                node_type = eventTku['event_categories'][0]
                if node_type == 'Virtual events':
                
                    # If the event is a virtual event, it is classified as  id virtual:public
                    eventItem ['location']['id'] = VIRTUAL_LOCATION_ID                                  
                elif str(eventTku['palvelukanava_code']) != '':

                    tprNo = str(eventTku['palvelukanava_code'])    
                    try: 
                        for trpNo in Place.objects.get(id=addressId):
                           
                            # Here we handle common errors or not found places
                            if tprNo == '10123': tprNo = '148'
                            if tprNo == '10132':
                                print("TPR 10132 does not compute") 
                                #time.sleep(2)
                                return
                            if tprNo == '10174':
                                print("TPR 10174 does not compute") 
                                #time.sleep(2)
                                return
                            if tprNo == '10129':
                                print("TPR 10129 does not compute") 
                                return
                              
                              # If not any error, the number of palvelukanava_code is used 
                            eventItem ['location']['id'] = ('tpr:' + tprNo)
                            print('eventItem: ' + tprNo)
                        
                    except:
                        print('Warning!' + ' TprNo not found in Place table:' + tprNo)
                        logger.info('Moderator should react.  TprNo not found in Place table:' + tprNo)    
                        pass
                   
                    

                else:
                    #This json address data is made by hand and it could be anything but a normal format is like
                    # 'Piispankatu 4, Turku' and it's modified to Linked Events Place Id mode like
                    # 'osoite:piispankatu_4_turku'
                    
                    if eventTku['address'] != None:
                        event_address = str(eventTku['address'])
                        
                        
                        #If turku is missing, we add turku
                        cityList = CITY_LIST

                        
                        # get rid of letters after street number
                        event_address = re.sub(r'([0-9])\s?[a-z](-[a-z])?$', r'\1', event_address.lower())



                        if 'turku' in event_address: 

                            if ')' in event_address:
                                event_address = event_address.split(')')
                                event_address = event_address[1]
                            
                            if ('turku' not in event_address) and (',' not in event_address):
                                event_address = event_address + ', turku'

                            event_address = event_address.split(',')

                           
                             #If city/municipality is missing, we add turku
                            
                            cityFound = False

                            for i in cityList:
                                
                                if i in event_address[1]:
                                    cityFound =True
                            
                            if not cityFound:
                                event_address[1] = event_address[1] + 'turku'         


                            lastLeterOffirstPart = event_address[0][-1:]
                            
                            #Here we check if street number is missing 
                            # If it is missing, we add 1
                            if not lastLeterOffirstPart.isdigit():
                                event_address[0] = event_address[0] + ' 1' 

                            #If Turku region postalcode (20xxx or 21xxxx) is found in address, it must be dropped out (space + 5 numbers = 6 char)
                            if " 2" in event_address[1]:
                                event_address[1] = event_address[1][6:]

                            event_address_data = event_address[0] + event_address[1]
                            event_address_data = event_address_data.replace(' ', '_')            
                            event_address_data = event_address_data.replace('k.', 'katu')

                            if event_address_data[0] == '_':
                                event_address_data = event_address_data[1:]

                           

                            #itäinen_pitkäkatu_64_a_1_turku

                           
                            #Check the locality of the address (turku)

                            addressIdParts = event_address_data.split('_')
                            addressId = 'osoite:'
                            isAddressFound = False

                            for p in addressIdParts: 
                                
                                place_id = None

                                addressId = (addressId + p) 
                                                  
                                try:

                                    place_id = Place.objects.get(id=addressId+"_turku")
                                
                                except:
                                    #NOTE! Save this in log file 
                                    logger.info('No matchs for address: ')
                                

                                if place_id:                                      

                                    event_address_data = addressId + "_turku"
                                    isAddressFound = True
                                    break 

                                addressId = addressId + '_'   

                            
                            addressId = 'osoite:'
                            
                            if not isAddressFound:
                               
                                time.sleep(3)
                                logger.info("-> IMPORTANT!!: Please add this address to the event_place database table: "+ event_address_data)
                                return

                            event_place_id = event_address_data

                            
                            eventItem ['location']['id'] = event_place_id

                        else:
                            logger.warning("No match found for place '%s' (event %s, %s)" % (eventTku['address'],
                                                                        eventTku['drupal_nid'], eventTku['title_fi']))    
                            
                            logger.info("No address found for event with ID: " + str(eventTku['drupal_nid']) + ", " + eventTku['title_fi'] +  ",(" + str(eventTku['address']) + ")")
          
            # Add a default offer
            free_offer = {
                'is_free': True,
                'price': None,
                'description': None,
                'info_url': None,
            }

            eventOffer_is_free = str(eventTku['free_event'])
            
            #Fill event_offer table information if events is not free price event
            if eventOffer_is_free == "0":
                        

                if eventTku['event_price'] != None: 
                    #get html tags out of string!                       
                    ok_tags = ('u', 'b', 'h2', 'h3', 'em', 'ul', 'li', 'strong', 'br', 'p', 'a')
                    price = str(eventTku['event_price'])                 
                    price = bleach.clean(price, tags= ok_tags, strip=True)                    
                    free_offer_price = clean_text(price, True)                       
                else: 
                    free_offer_price = 'No price'

                if str(eventTku['buy_tickets_url']) != None: 
                    free_offer_buy_tickets = eventTku['buy_tickets_url'] 
                else:
                    free_offer_buy_tickets = '' 
            
                free_offer['is_free'] = False
                free_offer['price'] = {'fi': free_offer_price}
                free_offer['description'] = ''
                free_offer['info_url'] =  {'fi': free_offer_buy_tickets}
            
            eventItem['offers'] = [free_offer]

            return eventItem

    def _recur_fetch_paginated_url(self, url, lang, events):
        max_tries = 5       
        for try_number in range(0, max_tries):            
            response = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
            if response.status_code != 200:
                logger.warning("tku Drupal orig API reported HTTP %d" % response.status_code)
                time.sleep(2)
            if self.cache:
                self.cache.delete_url(url)
                continue
            try:
                root_doc = response.json()
                time.sleep(2)
            except ValueError:
                logger.warning("tku Drupal orig API returned invalid JSON (try {} of {})".format(try_number + 1, max_tries))
                if self.cache:
                    self.cache.delete_url(url)
                    time.sleep(1)
                    continue
            break
        else:
            logger.error("tku Drupal orig API broken again, giving up")
            raise APIBrokenError()

        json_root_event = root_doc['events']
        earliest_end_time = None
        #This part loops through element by element in our JSON dump.


        event_image_url = None

                          
        #Here we check if the event is mother event because at first, we are not going to read in any child. 
        #After this , we find children for the mother event


        #Our mother event looper logic
        for json_mother_event in json_root_event:
            json_event = json_mother_event['event']
            if json_event['event_image_ext_url']:
                event_image_url = json_event['event_image_ext_url']['src']
          
            if json_event['event_type'] == "Single event" or json_event['event_type'] == "Event series":
                event = self._import_event(lang, json_event, events, event_image_url)
                
            
        now = datetime.now().replace(tzinfo=LOCAL_TZ)

    def saveChildElement(self, url, lang):
        max_tries = 5
        for try_number in range(0, max_tries):
            response = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
            if response.status_code != 200:
                logger.warning("tku Drupal orig API reported HTTP %d" % response.status_code)
                time.sleep(2)
            if self.cache:
                self.cache.delete_url(url)
                continue
            try:
                root_doc = response.json()
            except ValueError:
                logger.warning("tku Drupal orig API returned invalid JSON (try {} of {})".format(try_number + 1, max_tries))
                if self.cache:
                    self.cache.delete_url(url)
                    time.sleep(5)
                    continue
            break
        else:
            logger.error("tku Drupal orig API broken again, giving up")
            raise APIBrokenError()

        json_root_event = root_doc['events']
        earliest_end_time = None
       
       
        #This part loops through element by element in our JSON dump.
        #all children event must find their mothers 
        for json_event in json_root_event:
            json_event = json_event['event']
            eventTku = self._get_eventTku(json_event)
            if eventTku['event_type'] == "Recurring event (in series)":
                motherFound = self._import_child_event(lang, eventTku)
               
        now = datetime.now().replace(tzinfo=LOCAL_TZ)
    

    def import_events(self):
        
        logger.info("Importing old Turku events")
                
        events = recur_dict()
            
        url = TKUDRUPAL_BASE_URL
        
        lang = self.supported_languages

        try:

            #This calls the recur_fetch_paginated function.
            self._recur_fetch_paginated_url(url, lang, events)
        except APIBrokenError:
            return


        event_list = sorted(events.values(), key=lambda x: x['end_time'])

        #qs = Event.objects.filter(end_time__gte=datetime.now(), self.data_source, deleted=False)
        qs = Event.objects.filter(end_time__gte=datetime.now(), data_source='turku', deleted=False)
        self.syncher = ModelSyncher(qs, lambda obj: obj.origin_id, delete_func=mark_deleted)
        

        for event in event_list:
            obj = self.save_event(event)
            self.syncher.mark(obj)
           
    
        #self.syncher.finish(force=self.options['force'])
        self.syncher.finish(force=True)

       

        try:

            #This calls child element save funktion
            print("calls child element save funktioncalls child element save funktioncalls child element save funktioncalls child element save funktioncalls child element save funktioncalls child element save funktion")
            self.saveChildElement(url, lang)
        except APIBrokenError:
            return
       
        self.syncher.finish(force=True)
        logger.info("%d events processed" % len(events.values()))

        '''    
        print('LLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLapsetkin ajettu sisää!!!!!!!!!!')
        print('-Huom! tuntematon tpr:unit, joita esiintyy taajaa kaataa ohjelman. Lisää Try lohko ja lokikirjoitus!-') 
        print('----------------------------------- SE ON LOPPU NYT!!!-----------------------------------------------')
        print('----------Tarkista taulut : Event, Keyword, DataSource, Place, License, Image------------------------')
        print('----------Tarkista välitaulut taulut : eventlink, Event-in-Language, Event-Keyword, Event-License,---')
        print('----------Tarkista taulujen viiteavaimet Event_Place_id  Image_License id jne...---------------------')
        print('----------kirjoita logitiedostoon jos lädeaineistossa virheitä tai puutteita ym. moderoitavaa--------')
        print('----------poista debugaus ja työ kommentit ja kommentoi koodi ja lisää ajoohjeet---------------------')     
        '''