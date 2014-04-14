# -*- coding: utf-8 -*-
import requests
import requests_cache

import rdflib
from rdflib import URIRef
from rdflib import RDF
from rdflib.namespace import FOAF, SKOS, OWL

from events.models import Category, CategoryLabel, DataSource, BaseModel, Language

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
            name='Yleinen suomalainen ontologia',
            event_url_template='')
        self.data_source, _ = DataSource.objects.get_or_create(
            id=self.name, defaults=defaults)

    def import_categories(self):
        print("Importing YSO categories")
        graph = self.load_graph_into_memory(URL)
        self.save_categories(graph)

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

    def save_categories(self, graph):
        if self.verbosity >= 2:
            print("Saving data")
        data_source = DataSource.objects.get(pk='yso')

        bulk_mode = self.options.get('init', True)
        if not bulk_mode:
            delete_func = lambda obj: obj.delete()
            queryset = CategoryLabel.objects.filter(data_source=self.data_source)
            label_syncher = ModelSyncher(
                queryset, lambda obj: (obj.name, obj.language_id), delete_func=delete_func)

        category_labels = {}
        labels_to_create = set()
        for subject, label in graph.subject_objects(SKOS.altLabel):
            if (subject, RDF.type, SKOS.Concept) in graph:
                url = str(subject)
                if bulk_mode:
                    if label.language is not None:
                        labels_to_create.add((str(label), label.language))
                        if url not in category_labels:
                            category_labels[url] = []
                        category_labels[url].append(label)
                else:
                    label = self.save_alt_label(label_syncher, graph, label, data_source)
                    if label:
                        if subject not in category_labels:
                            category_labels[str(subject)] = []
                        category_labels[str(subject)].append(label)

        if bulk_mode:
            CategoryLabel.objects.bulk_create([
                CategoryLabel(
                    data_source=data_source,
                    name=name,
                    language_id=language
                ) for name, language in labels_to_create])
        else:
            label_syncher.finish()

        if bulk_mode:
            # self.save_labels_in_bulk(graph, data_source)
            self.save_categories_in_bulk(graph, data_source)
            self.save_category_label_relationships_in_bulk(category_labels)

        if not bulk_mode:
            queryset = Category.objects.filter(data_source=self.data_source)
            syncher = ModelSyncher(
                queryset, lambda obj: obj.url, delete_func=delete_func)
            save_set=set()
            for subject in graph.subjects(RDF.type, SKOS.Concept):
                self.save_category(syncher, graph, subject, data_source, category_labels, save_set)
            syncher.finish()

    def save_category_label_relationships_in_bulk(self, category_labels):
            categories = Category.objects.all().values('id', 'url')
            labels = CategoryLabel.objects.all().values('id', 'name', 'language')
            category_id_from_url = {
                c['url']: c['id'] for c in categories
            }
            label_id_from_name_and_language = {
                (l['name'], l['language']): l['id'] for l in labels
            }
            CategoryAltLabels = Category.alt_labels.through
            relations_to_create = []
            for url, url_labels in category_labels.items():
                for label in url_labels:
                    params = dict(
                        category_id = category_id_from_url.get(url),
                        categorylabel_id = (
                            label_id_from_name_and_language.get(
                                (str(label), label.language))))
                    if params['category_id'] and params['categorylabel_id']:
                        relations_to_create.append(
                            CategoryAltLabels(**params))
            CategoryAltLabels.objects.bulk_create(relations_to_create)

    def save_categories_in_bulk(self, graph, data_source):
        categories = []
        for subject in graph.subjects(RDF.type, SKOS.Concept):
            if is_deprecated(graph, subject):
                continue
            category = Category(data_source=data_source)
            category.aggregate = is_aggregate_concept(graph, subject)
            category.created_time = BaseModel.now()
            category.last_modified_time = BaseModel.now()
            category.url = str(subject)
            for _, literal in graph.preferredLabel(subject):
                with active_language(literal.language):
                    category.name = str(literal)
            categories.append(category)
        Category.objects.bulk_create(categories, batch_size=1000)

    def save_alt_label(self, syncher, graph, label, data_source):
        label_text = str(label)
        if label.language is None:
            print('Error:', str(label), 'has no language')
            return None
        label_object = syncher.get((label_text, str(label.language)))
        if label_object is None:
            language = Language.objects.get(id=label.language)
            label_object = CategoryLabel(
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

    def save_category(self, syncher, graph, subject, data_source, category_labels, save_set):
        category = syncher.get(subject)
        if not category:
            category = Category(
                data_source=self.data_source, url=subject)
            category._changed = True
            category._created = True
        else:
            category._created = False

        for _, literal in graph.preferredLabel(subject):
            with active_language(literal.language):
                if category.name != str(literal):
                    category.name = str(literal)
                    category._changed = True

        if category._changed:
            category.save()

        category.alt_labels.add(category_labels.get(str(subject), []))

        if not getattr(category, '_found', False):
            syncher.mark(category)
        return category
