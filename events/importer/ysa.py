# -*- coding: utf-8 -*-
import requests
import requests_cache

import rdflib
from rdflib import URIRef
from rdflib import RDF
from rdflib.namespace import FOAF, SKOS

from events.models import *

from sys import stdout
from .util import active_language
from .sync import ModelSyncher
from .base import Importer, register_importer


URLS = {
    'fi': 'http://finto.fi/rest/v1/ysa/data',
    'sv': 'http://finto.fi/rest/v1/allars/data'
}
DATASOURCES = {
    'fi': 'ysa',
    'sv': 'allars'
}

@register_importer
class YsaImporter(Importer):
    name = "ysa"

    def setup(self):
        requests_cache.install_cache('ysa')

    def import_categories(self):
        stdout.write("Importing YSA and Allärs categories")
        for lang, url in URLS.items():
            graph = load_graph_into_memory(url)
            self.save_categories(lang, graph)

    def load_graph_into_memory(self, url):
        resp = requests.get(url)
        assert resp.status_code == 200
        resp.encoding = 'UTF-8'
        graph = rdflib.Graph()
        graph.parse(data=resp.text, format='turtle')
        return graph

    def save_categories(self, lang, graph):
        data_source = DataSource.objects.get(pk=DATASOURCES[lang])
        for subject in graph.subjects(RDF.type, SKOS.Concept):
             self.save_category(graph, subject, data_source)

    def save_category(self, graph, subject, data_source):
        parent_category_subject = graph.value(
            subject=subject,
            predicate=SKOS.broader
        )
        if parent_category_subject is None:
            parent_category = None
        else:
            parent_category = self.save_category(graph, parent_category_subject, data_source)
        translation_objects = graph.objects(
            subject=subject,
            predicate=SKOS.exactMatch
        )
        ocount = len(list(translation_objects))
        if ocount > 1:
            print('exceptional translations: %d %s' % (ocount, str(subject)))
        translation_subject = graph.value(
            subject=subject,
            predicate=SKOS.exactMatch
        )
        alt_labels = graph.objects(
            subject=subject,
            predicate=SKOS.altLabel
        )
        # todo: update & delete
        category, created = Category.objects.get_or_create(
            url=str(subject),
            defaults={
                'data_source': data_source,
                'label': graph.preferredLabel(subject)[0][1],
                'parent_category': parent_category,
                'same_as': str(translation_subject)
            }
        )
        for l in alt_labels:
            l, created = CategoryLabel.objects.get_or_create(
                label=str(l))
            category.labels.add(l)

        l, created = CategoryLabel.objects.get_or_create(
            label=graph.preferredLabel(subject)[0][1]
        )
        category.labels.add(l)
        return category
