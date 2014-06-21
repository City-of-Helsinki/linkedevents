# -*- coding: utf-8 -*-
import requests
import requests_cache

import rdflib
from rdflib import URIRef
from rdflib import RDF
from rdflib.namespace import FOAF, SKOS, OWL

from events.models import Keyword, KeywordLabel, DataSource, BaseModel, Language, Organization

from sys import stdout
from .util import active_language
from .sync import ModelSyncher
from .base import Importer, register_importer

yso = rdflib.Namespace('http://www.yso.fi/onto/yso/')
URL = 'http://finto.fi/rest/v1/yso/data'

def is_deprecated(graph, subject):
    return (subject, OWL.deprecated, None) in graph
def is_aggregate_concept(graph, subject):
    return (subject, SKOS.inScheme, rdflib.term.URIRef(yso+'aggregateconceptscheme')) in graph

@register_importer
class YsoImporter(Importer):
    name = "yso"
    supported_languages = ['fi', 'sv', 'en']

    def setup(self):
        requests_cache.install_cache('yso')
        defaults = dict(
            name='Yleinen suomalainen ontologia')
        self.data_source, _ = DataSource.objects.get_or_create(
            id=self.name, defaults=defaults)

        ds_args = dict(id='system')
        defaults = dict(name='System')
        system_ds, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        org_args = dict(id='hy:kansalliskirjasto')
        defaults = dict(name='Kansalliskirjasto', data_source=system_ds)
        self.organization, _ = Organization.objects.get_or_create(defaults=defaults, **org_args)

    def import_keywords(self):
        print("Importing YSO keywords")
        graph = self.load_graph_into_memory(URL)
        self.save_keywords(graph)

    def load_graph_into_memory(self, url):
        if self.verbosity >= 2:
            print("Fetching %s" % url)
        resp = requests.get(url)
        assert resp.status_code == 200
        resp.encoding = 'UTF-8'
        graph = rdflib.Graph()
        if self.verbosity >= 2:
            print("Parsing RDF")
        graph.parse(data=resp.text, format='turtle')
        return graph

    def save_keywords(self, graph):
        if self.verbosity >= 2:
            print("Saving data")
        data_source = DataSource.objects.get(pk='yso')

        assert not Keyword.objects.filter(data_source=self.data_source).exists()
        bulk_mode = True
        if not bulk_mode:
            delete_func = lambda obj: obj.delete()
            queryset = KeywordLabel.objects.filter(data_source=self.data_source)
            label_syncher = ModelSyncher(
                queryset, lambda obj: (obj.name, obj.language_id), delete_func=delete_func)

        keyword_labels = {}
        labels_to_create = set()
        for subject, label in graph.subject_objects(SKOS.altLabel):
            if (subject, RDF.type, SKOS.Concept) in graph:
                yid = self.yso_id(subject)
                if bulk_mode:
                    if label.language is not None:
                        labels_to_create.add((str(label), label.language))
                        keyword_labels.setdefault(yid, []).append(label)
                else:
                    label = self.save_alt_label(label_syncher, graph, label, data_source)
                    if label:
                        keyword_labels.setdefault(yid, []).append(label)

        if bulk_mode:
            KeywordLabel.objects.bulk_create([
                KeywordLabel(
                    name=name,
                    language_id=language
                ) for name, language in labels_to_create])
        else:
            label_syncher.finish()

        if bulk_mode:
            # self.save_labels_in_bulk(graph, data_source)
            self.save_keywords_in_bulk(graph, data_source)
            self.save_keyword_label_relationships_in_bulk(keyword_labels)

        if not bulk_mode:
            queryset = Keyword.objects.filter(data_source=self.data_source)
            syncher = ModelSyncher(
                queryset, lambda obj: obj.url, delete_func=delete_func)
            save_set=set()
            for subject in graph.subjects(RDF.type, SKOS.Concept):
                self.save_keyword(syncher, graph, subject, data_source, keyword_labels, save_set)
            syncher.finish()

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
                    keyword_id = yid,
                    keywordlabel_id = (
                        label_id_from_name_and_language.get(
                            (str(label), label.language))))
                if params['keyword_id'] and params['keywordlabel_id']:
                    relations_to_create.append(
                        KeywordAltLabels(**params))
        KeywordAltLabels.objects.bulk_create(relations_to_create)

    def yso_id(self, subject):
        return ':'.join(subject.split('/')[-2:])

    def save_keywords_in_bulk(self, graph, data_source):
        keywords = []
        for subject in graph.subjects(RDF.type, SKOS.Concept):
            if is_deprecated(graph, subject):
                continue
            keyword = Keyword(data_source=data_source)
            keyword.aggregate = is_aggregate_concept(graph, subject)
            keyword.id = self.yso_id(subject)
            keyword.created_time = BaseModel.now()
            keyword.last_modified_time = BaseModel.now()
            for _, literal in graph.preferredLabel(subject):
                with active_language(literal.language):
                    keyword.name = str(literal)
            keywords.append(keyword)
        Keyword.objects.bulk_create(keywords, batch_size=1000)

    def save_alt_label(self, syncher, graph, label, data_source):
        label_text = str(label)
        if label.language is None:
            print('Error:', str(label), 'has no language')
            return None
        label_object = syncher.get((label_text, str(label.language)))
        if label_object is None:
            language = Language.objects.get(id=label.language)
            label_object = KeywordLabel(
                name=label_text, language=language, data_source=data_source)
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

    def save_keyword(self, syncher, graph, subject, data_source, keyword_labels, save_set):
        keyword = syncher.get(subject)
        if not keyword:
            keyword = Keyword(
                data_source=self.data_source, url=subject)
            keyword._changed = True
            keyword._created = True
        else:
            keyword._created = False

        for _, literal in graph.preferredLabel(subject):
            with active_language(literal.language):
                if keyword.name != str(literal):
                    keyword.name = str(literal)
                    keyword._changed = True

        if keyword._changed:
            keyword.save()

        keyword.alt_labels.add(keyword_labels.get(str(subject), []))

        if not getattr(keyword, '_found', False):
            syncher.mark(keyword)
        return keyword
