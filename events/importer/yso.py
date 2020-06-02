# -*- coding: utf-8 -*-
import requests
import logging

import rdflib
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django_orghierarchy.models import Organization
from django_orghierarchy.models import OrganizationClass
from rdflib import RDF
from rdflib.namespace import DCTERMS, OWL, SKOS

from events.models import Keyword, KeywordLabel, DataSource, BaseModel, Language

from .util import active_language
from .sync import ModelSyncher
from .base import Importer, register_importer

# Per module logger
logger = logging.getLogger(__name__)

yso = rdflib.Namespace('http://www.yso.fi/onto/yso/')
URL = 'http://finto.fi/rest/v1/yso/data'

YSO_DEPRECATED_MAPS = {
    'yso:p12262': 'yso:p4354',  # lapset (kooste) -> lapset (ikään liittyvä rooli), missing YSO replacement
    'yso:p21160': 'yso:p8113',  # kirjallisuus (erikoisala) -> kirjallisuus (taidelajit), wrong YSO replacement
}

# yso keywords for the importers to automatically include in the audience field as well

#This is not used anywhere in the Turku specific project for now.
KEYWORDS_TO_ADD_TO_AUDIENCE = [
    'p4354',
    'p11617',
    'p2433',
    'p4363',
    'p6165',
    'p16485',
    'p1178',
    'p16486',
    'p1393',
    'p1178',
    'p9607',
    'p7179',
    'p16596',
]

def get_yso_id(subject):
    # we must validate the id, yso API might contain invalid data
    try:
        data_source, origin_id = subject.split('/')[-2:]
    except ValueError:
        raise ValidationError('Subject ' + subject + ' has invalid YSO id')
    if data_source != 'yso':
        raise ValidationError('Subject ' + subject + ' has invalid YSO id')
    return ':'.join((data_source, origin_id))


def get_subject(yso_id):
    return rdflib.term.URIRef(yso + yso_id.split(':')[-1])


def is_deprecated(graph, subject):
    return (subject, OWL.deprecated, None) in graph


def is_aggregate_concept(graph, subject):
    return (subject, SKOS.inScheme, rdflib.term.URIRef(yso + 'aggregateconceptscheme')) in graph


def get_replacement(graph, subject):
    for subject, verb, object in graph.triples((subject, DCTERMS.isReplacedBy, None)):
        return object


def deprecate_and_replace(graph, keyword):
    if keyword.id in YSO_DEPRECATED_MAPS:
        # these ones need no further processing
        return keyword.deprecate()
    replacement_subject = get_replacement(graph, get_subject(keyword.id))
    new_keyword = None
    if replacement_subject:
        try:
            # not all the replacements are valid keywords. yso has some data quality issues
            new_keyword = Keyword.objects.get(id=get_yso_id(replacement_subject))
        except Keyword.DoesNotExist:
            pass
    if new_keyword:
        logger.info('Keyword %s replaced by %s' % (keyword, new_keyword))
        new_keyword.events.add(*keyword.events.all())
        new_keyword.audience_events.add(*keyword.audience_events.all())
    else:
        logger.info('Keyword %s deprecated without replacement!' % keyword)
        if keyword.events.all().exists() or keyword.audience_events.all().exists():
            raise Exception("Deprecating YSO keyword %s that is referenced in events %s. "
                            "No replacement keyword was found in YSO. Please manually map the "
                            "keyword to a new keyword in YSO_DEPRECATED_MAPS." %
                            (str(keyword), str(keyword.events.all() | keyword.audience_events.all())))
    return keyword.deprecate() and keyword.replace(new_keyword)


@register_importer
class YsoImporter(Importer):
    name = "yso"
    supported_languages = ['fi', 'sv', 'en']

    def setup(self):
        defaults = dict(
        name='Yleinen suomalainen ontologia')
        self.data_source, _ = DataSource.objects.get_or_create(
            id=self.name, defaults=defaults)       

        #public data sourse for organisations model
        ds_args1 = dict(id='org', user_editable=True)
        defaults1 = dict(name='Ulkoa tuodut organisaatiotiedot')
        self.data_source1, _ = DataSource.objects.get_or_create(defaults=defaults1, **ds_args1)  

        #public organizations class for all instans (this includes also city of Turku specifig organization class)
        ds_args = dict(origin_id='13', data_source=self.data_source1)
        defaults = dict(name='Sanasto')
        self.organizationclass13, _ =  OrganizationClass.objects.get_or_create(defaults=defaults, **ds_args)
        
        org_args = dict(origin_id='1200', data_source=self.data_source, classification_id="org:13")
        defaults = dict(name='YSO')
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

    def import_keywords(self):
        logger.info("Importing YSO keywords")
        graph = self.load_graph_into_memory(URL)
        self.save_keywords(graph)

    def load_graph_into_memory(self, url):
        logger.debug("Fetching %s" % url)
        resp = requests.get(url)
        assert resp.status_code == 200
        resp.encoding = 'UTF-8'
        graph = rdflib.Graph()
        logger.debug("Parsing RDF")
        graph.parse(data=resp.text, format='turtle')
        return graph

    def save_keywords(self, graph):
        logger.debug("Saving data")

        bulk_mode = False
        if bulk_mode:
            assert not Keyword.objects.filter(data_source=self.data_source).exists()
        if not bulk_mode:
            queryset = KeywordLabel.objects.all()
            label_syncher = ModelSyncher(
                queryset, lambda obj: (obj.name, obj.language_id), delete_func=lambda obj: obj.delete())

        keyword_labels = {}
        labels_to_create = set()
        for subject, label in graph.subject_objects(SKOS.altLabel):
            if (subject, RDF.type, SKOS.Concept) in graph:
                try:
                    yid = get_yso_id(subject)
                    if bulk_mode:
                        if label.language is not None:
                            language = label.language
                            if label.language == 'se':
                                # YSO doesn't contain se, assume an error.
                                language = 'sv'
                            labels_to_create.add((str(label), language))
                            keyword_labels.setdefault(yid, []).append(label)
                    else:
                        label = self.save_alt_label(label_syncher, graph, label)
                        if label:
                            keyword_labels.setdefault(yid, []).append(label)
                except ValidationError as e:
                    logger.error(e)

        if bulk_mode:
            KeywordLabel.objects.bulk_create([
                KeywordLabel(
                    name=name,
                    language_id=language
                ) for name, language in labels_to_create])
        else:
            label_syncher.finish(force=self.options['force'])

        if bulk_mode:
            self.save_keywords_in_bulk(graph)
            self.save_keyword_label_relationships_in_bulk(keyword_labels)

        if not bulk_mode:
            # manually add new keywords to deprecated ones
            for old_id, new_id in YSO_DEPRECATED_MAPS.items():
                try:
                    old_keyword = Keyword.objects.get(id=old_id)
                    new_keyword = Keyword.objects.get(id=new_id)
                except ObjectDoesNotExist:
                    continue
                logger.info('Manually mapping events with %s to %s' % (str(old_keyword), str(new_keyword)))
                new_keyword.events.add(*old_keyword.events.all())
                new_keyword.audience_events.add(*old_keyword.audience_events.all())

            queryset = Keyword.objects.filter(data_source=self.data_source, deprecated=False)
            syncher = ModelSyncher(
                queryset, lambda keyword: keyword.id,
                delete_func=lambda obj: deprecate_and_replace(graph, obj),
                check_deleted_func=lambda obj: obj.deprecated)
            save_set = set()
            for subject in graph.subjects(RDF.type, SKOS.Concept):
                try:
                    self.save_keyword(syncher, graph, subject, keyword_labels, save_set)
                except ValidationError as e:
                    logger.error(e)
            syncher.finish(force=self.options['force'])

    def save_keyword_label_relationships_in_bulk(self, keyword_labels):
        yids = Keyword.objects.all().values_list('id', flat=True)
        labels = KeywordLabel.objects.all().values('id', 'name', 'language')
        label_id_from_name_and_language = {
            (l['name'], l['language']): l['id'] for l in labels
        }
        KeywordAltLabels = Keyword.alt_labels.through
        relations_to_create = []
        for yid, url_labels in keyword_labels.items():
            if yid not in yids:
                continue
            for label in url_labels:
                params = dict(
                    keyword_id=yid,
                    keywordlabel_id=(
                        label_id_from_name_and_language.get(
                            (str(label), label.language))))
                if params['keyword_id'] and params['keywordlabel_id']:
                    relations_to_create.append(
                        KeywordAltLabels(**params))
        KeywordAltLabels.objects.bulk_create(relations_to_create)

    def create_keyword(self, graph, subject):
        if is_deprecated(graph, subject):
            return
        keyword = Keyword(data_source=self.data_source)
        keyword._created = True
        keyword.id = get_yso_id(subject)
        keyword.created_time = BaseModel.now()
        keyword.aggregate = is_aggregate_concept(graph, subject)
        self.update_keyword(keyword, graph, subject)
        return keyword

    def update_keyword(self, keyword, graph, subject):
        for _, literal in graph.preferredLabel(subject):
            with active_language(literal.language):
                if keyword.name != str(literal):
                    logger.debug('(re)naming keyword ' + keyword.name + ' to ' + str(literal))
                    keyword.name = str(literal)
                    keyword._changed = True
                    keyword.last_modified_time = BaseModel.now()

    def save_keywords_in_bulk(self, graph):
        keywords = []
        for subject in graph.subjects(RDF.type, SKOS.Concept):
            keyword = self.create_keyword(graph, subject)
            if keyword:
                keywords.append(keyword)
        Keyword.objects.bulk_create(keywords, batch_size=1000)

    def save_alt_label(self, syncher, graph, label):
        label_text = str(label)
        if label.language is None:
            logger.error('Error: {} has no language'.format(label))
            return None
        label_object = syncher.get((label_text, str(label.language)))
        if label_object is None:
            language = Language.objects.get(id=label.language)
            label_object = KeywordLabel(
                name=label_text, language=language)
            label_object._changed = True
            label_object._created = True
        else:
            label_object._created = False
        if label_object._created:
            # Since there are duplicates, only save & mark them once.
            label_object.save()

        if not getattr(label_object, '_found', False):
            syncher.mark(label_object)
        return label_object

    def save_keyword(self, syncher, graph, subject, keyword_labels, save_set):
        if is_deprecated(graph, subject):
            return
        keyword = syncher.get(get_yso_id(subject))
        if not keyword:
            keyword = self.create_keyword(graph, subject)
            if not keyword:
                return
        else:
            keyword._created = False
            self.update_keyword(keyword, graph, subject)

        if keyword.publisher_id != self.organization.id:
            keyword.publisher = self.organization
            keyword._changed = True
        if keyword._changed:
            keyword.save()

        alt_labels = keyword_labels.get(get_yso_id(subject), [])
        keyword.alt_labels.add(*alt_labels)

        if not getattr(keyword, '_found', False):
            syncher.mark(keyword)
        return keyword
