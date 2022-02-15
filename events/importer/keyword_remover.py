# -*- coding: utf-8 -*-

# Developer note! This is a temporary importer solely to fix a bug. Will be removed at a later stage.

# Dependencies.

# RDFLIB:
import rdflib
from rdflib import RDF, URIRef
from rdflib.namespace import DCTERMS, OWL, SKOS

# Logging:
import time
import math
import logging
from os import mkdir
from os.path import abspath, join, dirname, exists, basename, splitext

# Django:
from django_orghierarchy.models import Organization
from django_orghierarchy.models import OrganizationClass
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from events.models import Keyword, KeywordLabel, DataSource, BaseModel, Language

# Importer specific:
from .base import Importer, register_importer

# Type checking:
from typing import TYPE_CHECKING, Any, Tuple, List

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

def proc_time_frmt(stage) -> None:
    ft = math.modf(time.process_time())
    curtime = float(str(ft[0])[:3])+ft[1]
    logger.info("%s finished after %s seconds from the initial start!" % (stage, curtime))

@register_importer
class KeywordRemoverImporter(Importer):
    # Importer class dependant attributes:
    name = "keyword_remover"  # Command calling name.
    supported_languages = ['fi', 'sv', 'en']  # Base file requirement.

    def iterator(self, data: dict, key: str, query: Any, obj_model: tuple, attr_map: tuple) -> None:
        ''' 
        Main class data logic. Create DB objects & set class attributes.
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

    def setup(self) -> None:
        self.data = {
            # YSO, JUPO and the Public DataSource for Organizations model.
            'ds': {
                'yso': ('yso', 'Yleinen suomalainen ontologia', True),
                'org': ('org', 'Ulkoa tuodut organisaatiotiedot', True),
            },
            # Public organization class for all instances.
            'orgclass': {
                'sanasto': ['org:13', '13', 'Sanasto', BaseModel.now(), 'ds_org'],
            },
            # General ontology organization for keywords.
            'org': {
                'yso': ['yso:1200', '1200', 'YSO', BaseModel.now(), 'org:13', 'ds_yso']
            },
            # Attribute name mapping for all due to class related attributes (ex. data_source and organization are necessary).
            'attr_maps': {
                'ds': ('data_source', 'data_source_org'),
                'orgclass': ('organization_class_13', ),
                'org': ('organization', ),
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
        proc_time_frmt("Setup")
        self.handle()

    def remover(self, onto) -> None:
        Keyword.objects.filter(data_source__id=onto).delete()

    def handle(self) -> None:
        # Handler function for passing the graph between functions. More organized at the cost of more function calls.
        self.remover('jupo')
        proc_time_frmt("Importer")
