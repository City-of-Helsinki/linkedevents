# -*- coding: utf-8 -*-
import requests
import requests_cache

import rdflib
from rdflib import URIRef
from rdflib import RDF
from rdflib.namespace import FOAF, SKOS

from events.models import *

from util import active_language

from .sync import ModelSyncher
from .base import Importer, register_importer


URLS = {
    'fi': 'http://finto.fi/rest/v1/ysa/data',
    'sv': 'http://finto.fi/rest/v1/allars/data'
}


@register_importer
class YsaImporter(Importer):
    name = "ysa"
    data_source = DataSource.objects.get(pk=name)

    def setup(self):
        requests_cache.install_cache('ysa')

    def import_categories(self):
        print("Importing YSA and Allärs categories")
        for lang, url in URLS.iteritems():
            resp = requests.get(url)
            assert resp.status_code == 200
            graph = rdflib.Graph()
            graph.parse(data=resp.text, format='turtle')
            self.save_categories(lang, graph)

    def save_categories(self, lang, graph):
        with active_language(lang):
            for subject in graph.subjects(RDF.type, SKOS.Concept):
                self.save_category(graph, subject)

    def save_category(self, graph, subject):
        parent_category_subject = graph.value(
            subject=subject,
            predicate=SKOS.broader
        )
        if parent_category_subject is None:
            parent_category = None
        else:
            parent_category = self.save_category(graph, parent_category_subject)
        translation_subject = graph.value(
            subject=subject,
            predicate=SKOS.exactMatch
        )
        try:
            translation = Category.objects.get(url=translation_subject)
        except Category.DoesNotExist:
            translation = None
        if not Category.objects.filter(url=unicode(subject)).exists():
            category=Category(
                url=unicode(subject),
                label=graph.preferredLabel(subject)[0][1],
                parent_category=parent_category,
                same_as=translation
            )
            category.save()
            return category
        return None
