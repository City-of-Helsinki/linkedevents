# -*- coding: utf-8 -*-

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

def fetch_graph() -> dict:
    # Generate graph base, and parse the file.
    try:
        graph = rdflib.Graph()
        graph.parse('http://finto.fi/rest/v1/yso/data')
    except Exception as e:
        logger.error("Error while fetching YSO Graph file: %s" % e)
    # LICENSE http://creativecommons.org/licenses/by/3.0/: https://finto.fi/jupo/fi/
    proc_time_frmt("Graph fetch & parsing")
    return graph

def uri_format(subj_uriRef) -> str:
    subj_type, subj_id = subj_uriRef.split('/')[-2:]
    formatted_onto = "%s:%s" % (subj_type, subj_id)
    return subj_type, subj_id, formatted_onto

@register_importer
class OntologyImporter(Importer):
    # Importer class dependant attributes:
    name = "ontology"  # Command calling name.
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

    def process_graph(self, graph: dict) -> Tuple[dict, List[Any]]:
        processed = {}
        deprecated = []
        '''
        The metatag is not the @prefix name, it is the one used in the uriRef formatting;
        ex. @prefix yso-meta1: <http://www.yso.fi/onto/yso-meta/> .
        In case you want to use a special ontology file with multiple ontologies, feel free to map them here:
        '''
        specifications = {
            'yso': {
                'types': (
                    ('Concept', 1), # Structural similarity to the ontology_type implementation in the models.
                    ('Individual', 1),
                    ('Hierarchy', 2)
                ),
                'meta': ('yso-meta', ),
            },
        }

        # Loop through all Concepts. Includes deprecated and regular.
        for subj_uriRef in graph.subjects(predicate=None, object=SKOS.Concept):
            subj_type, subj_id, formatted_onto = uri_format(subj_uriRef)
            if subj_type in specifications.keys():
                sub_skos = {
                    'altLabel': {'fi': None, 'sv': None, 'en': None},
                    'prefLabel': {'fi': None, 'sv': None, 'en': None},
                    'broader': [],
                    'narrower': [],
                    'ontoType': None
                }

                for types in specifications[subj_type]['types']:
                    for meta in specifications[subj_type]['meta']:
                        mkuriref = rdflib.term.URIRef(
                            'http://www.yso.fi/onto/%s/%s' % (meta, types[0]))
                        if (subj_uriRef, None, mkuriref) in graph:
                            ot = types[0]

                # Gather labels: altLabel, prefLabel, broader, narrower.
                for label, v in sub_skos.items():
                    for obj in graph.objects(subject=subj_uriRef, predicate=SKOS[label]):
                        if isinstance(v, dict):
                            v.update(
                                dict({str(obj.language): str(obj.value)}))
                        else:
                            v.append(obj)

                if (subj_uriRef, OWL.deprecated, None) in graph:
                    ot = 'Concept'
                    isReplacedBy = None
                    for _, _, object in graph.triples((subj_uriRef, DCTERMS.isReplacedBy, None)):
                        _, _, formatted_obj = uri_format(object)
                        isReplacedBy = formatted_obj
                    deprecated.append([formatted_onto, isReplacedBy])

                sub_skos.update({
                    'type': subj_type,
                    'id': subj_id,
                    'ontoType': dict(specifications['yso']['types'])[ot]
                    })
                processed.update(dict({formatted_onto: sub_skos}))

        proc_time_frmt("Graph processing")
        return processed, deprecated

    def save_alt_keywords(self, processed: dict) -> None:
        for k in processed:
            altk = processed[k]['altLabel']
            for lang in altk:
                altlang = altk[lang]
                if altlang:
                    try:
                        # Check duplicates:
                        alt_label_exists = KeywordLabel.objects.filter(
                            name=altlang).exists()
                        if not alt_label_exists:
                            language = Language.objects.get(id=lang)
                            label_object = KeywordLabel(
                                name=altlang, language=language)
                            label_object.save()
                    except Exception as e:
                        logger.error("Error: %s for alt keyword obj %s with language %s" % (e, altk, lang))
        proc_time_frmt("Alt keywords saving")

    def save_keywords(self, processed: dict) -> None:
        for k, v in processed.items():
            try:
                keyword = Keyword(data_source=getattr(self, 'data_source'))
                keyword.id = k
                keyword.created_time = BaseModel.now()
                for lang, lang_val in v['prefLabel'].items():
                    langformat = 'name_%s' % lang
                    setattr(keyword, langformat, lang_val)
                keyword.ontology_type = v['ontoType']
                keyword.origin_id = v['id']
                keyword.publisher = getattr(self, 'organization')
                keyword.save()
                alts = []
                # Link ManyToMany relation alt label values.
                for alt_lang in v['altLabel']:
                    alt_obj = v['altLabel'][alt_lang]
                    cur_obj = None
                    try:
                        cur_obj = KeywordLabel.objects.filter(
                            name=alt_obj, language_id=alt_lang).first()
                    except Exception as e:
                        logger.error(e)
                    if cur_obj:
                        alts.append(cur_obj)
                if alts:
                    keyword.alt_labels.add(*alts)
                    keyword.save()
            except Exception as e:
                logger.error(e)
        proc_time_frmt("Keywords saving")

    def graph_relation(self, processed: dict) -> None:
        # Relations are established between the keywords after they are all saved to the DB.
        def _get_pc(p_c):
            found_pcs = []
            for pc in v[p_c]:
                _, _, formatted_obj = uri_format(pc)
                try:
                    found_pc = Keyword.objects.get(id=formatted_obj)
                    found_pcs.append(found_pc)
                except Exception as e:
                    logger.warn('Could not find %s %s with warning: %s' % (p_c, formatted_obj, e))
            return found_pcs

        for k, v in processed.items():
            try:
                curObj = Keyword.objects.get(id=k)
                curObj.parents.add(*_get_pc('broader'))
                curObj.children.add(*_get_pc('narrower'))
                curObj.save()
            except Exception as e:
                logger.error(e)
        proc_time_frmt("Graph relation generation")

    def mark_deprecated(self, deprecated: dict) -> None:
        for value in deprecated:
            onto = value[0]
            replacement = value[1]

            try:
                kw = Keyword.objects.get(id=onto)
                kw.deprecated = True
                kw.created_time = BaseModel.now()
                kw.save()
            except Exception as e:
                logger.warn(
                    'Could not deprecate keyword %s with error: %s' % (onto, e))
                continue
            
            if replacement:
                try:
                    replaced_kw = Keyword.objects.get(id=replacement)
                    kw.replaced_by = replaced_kw
                    kw.created_time = BaseModel.now()
                    kw.save()
                except Exception as e:
                    logger.warn(
                        'Could not find replacement key in the database for %s with replacement key_id: %s with error: %s' % (onto, replacement, e))
                    continue
            else:
                logger.warn('Replacement for deprecated keyword %s is None.' % onto)
        proc_time_frmt("Marked deprecated keywords")

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

    def handle(self) -> None:
        # Handler function for passing the graph between functions. More organized at the cost of more function calls.
        self.graph = fetch_graph()
        self.processed, self.deprecated = self.process_graph(graph=self.graph)
        self.save_alt_keywords(processed=self.processed)
        self.save_keywords(processed=self.processed)
        self.graph_relation(processed=self.processed)
        self.mark_deprecated(self.deprecated)
        proc_time_frmt("Importer")
