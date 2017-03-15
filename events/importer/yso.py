# -*- coding: utf-8 -*-
import requests
import requests_cache

import rdflib
from django.core.exceptions import ObjectDoesNotExist
from rdflib import URIRef
from rdflib import RDF
from rdflib.namespace import FOAF, SKOS, OWL

from django.conf import settings

from events.models import Keyword, KeywordLabel, DataSource, BaseModel, Language, Organization

from sys import stdout
from .util import active_language
from .sync import ModelSyncher
from .base import Importer, register_importer

yso = rdflib.Namespace('http://www.yso.fi/onto/yso/')
URL = 'http://finto.fi/rest/v1/yso/data'

YSO_DEPRECATED_MAPS = {
    'yso:p11125': 'yso:p3602',  # tilat (kooste) -> tilat
    'yso:p23756': 'yso:p2625',  # teatteri (kooste) -> teatteri
    'yso:p12262': 'yso:p4354',  # lapset (kooste) -> lapset (ikäryhmät)
    'yso:p21160': 'yso:p8113',  # kirjallisuus (erikoisala) -> kirjallisuus
    'yso:p19403': 'yso:p11693',  # musikaalit (kooste) -> musikaalit
    'yso:p21510': 'yso:p1808',  # musiikki (erikoisala) -> musiikki
    'yso:p22439': 'yso:p1808',  # musiikki (kooste) -> musiikki
    'yso:p22047': 'yso:p1278',  # tanssi (kooste) -> tanssi
    'yso:p20433': 'yso:p12307',  # valokuvaajat (kooste) -> valokuvaajat
}

def is_deprecated(graph, subject):
    return (subject, OWL.deprecated, None) in graph
def is_aggregate_concept(graph, subject):
    return (subject, SKOS.inScheme, rdflib.term.URIRef(yso+'aggregateconceptscheme')) in graph
def allow_deprecating_keyword(keyword):
    if keyword.events.all().exists() or keyword.audience_events.all().exists():
        if keyword.id not in YSO_DEPRECATED_MAPS:
            raise Exception("Deprecating YSO keyword %s that is referenced in events %s. "
                            "No replacement keyword was found in YSO altLabels. Please manually map the "
                            "keyword to a new keyword in YSO_DEPRECATED_MAPS." %
                            (str(keyword), str(keyword.events.all() | keyword.audience_events.all())))
    return True


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

        ds_args = dict(id=settings.SYSTEM_DATA_SOURCE_ID)
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

        bulk_mode = False
        if bulk_mode:
            assert not Keyword.objects.filter(data_source=self.data_source).exists()
        if not bulk_mode:
            delete_func = lambda obj: obj.delete()
            queryset = KeywordLabel.objects.all()
            label_syncher = ModelSyncher(
                queryset, lambda obj: (obj.name, obj.language_id), delete_func=delete_func)

        keyword_labels = {}
        labels_to_create = set()
        for subject, label in graph.subject_objects(SKOS.altLabel):
            if (subject, RDF.type, SKOS.Concept) in graph:
                yid = self.yso_id(subject)
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

        if bulk_mode:
            KeywordLabel.objects.bulk_create([
                KeywordLabel(
                    name=name,
                    language_id=language
                ) for name, language in labels_to_create])
        else:
            label_syncher.finish()

        if bulk_mode:
            self.save_keywords_in_bulk(graph)
            self.save_keyword_label_relationships_in_bulk(keyword_labels)

        if not bulk_mode:
            deprecate_keyword = lambda obj: obj.deprecate()
            check_deprecated_keyword = lambda obj: obj.deprecated
            # manually add new keywords to deprecated ones
            for old_id, new_id in YSO_DEPRECATED_MAPS.items():
                try:
                    old_keyword = Keyword.objects.get(id=old_id)
                    new_keyword = Keyword.objects.get(id=new_id)
                except ObjectDoesNotExist:
                    continue
                print('Mapping events with %s to %s' % (str(old_keyword), str(new_keyword)))
                new_keyword.events.add(*old_keyword.events.all())
                new_keyword.audience_events.add(*old_keyword.audience_events.all())

            queryset = Keyword.objects.filter(data_source=self.data_source, deprecated=False)
            syncher = ModelSyncher(
                queryset, lambda keyword: keyword.id,
                delete_func=deprecate_keyword,
                check_deleted_func=check_deprecated_keyword,
                allow_deleting_func=allow_deprecating_keyword)
            save_set=set()
            for subject in graph.subjects(RDF.type, SKOS.Concept):
                self.save_keyword(syncher, graph, subject, keyword_labels, save_set)
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

    def create_keyword(self, graph, subject):
        if is_deprecated(graph, subject):
            return
        keyword = Keyword(data_source=self.data_source)
        keyword._changed = True
        keyword._created = True
        keyword.aggregate = is_aggregate_concept(graph, subject)
        keyword.id = self.yso_id(subject)
        keyword.created_time = BaseModel.now()
        keyword.last_modified_time = BaseModel.now()
        for _, literal in graph.preferredLabel(subject):
            with active_language(literal.language):
                keyword.name = str(literal)
        return keyword

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
            print('Error:', str(label), 'has no language')
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
        keyword = syncher.get(self.yso_id(subject))
        if not keyword:
            keyword = self.create_keyword(graph, subject)
            if not keyword:
                return
        else:
            keyword._created = False
        if keyword._changed:
            keyword.save()

        alt_labels = keyword_labels.get(self.yso_id(subject), [])
        keyword.alt_labels.add(*alt_labels)
        # Finnish alt labels might refer to old keywords, add any new keywords to events
        for label in alt_labels:
            if not label.language == Language.objects.get(id='fi'):
                continue
            old_keyword = Keyword.objects.filter(
                data_source=self.data_source).filter(name_fi=label.name).first()
            if not old_keyword:
                continue
            print('Keyword ' + str(old_keyword) + ' may have been deprecated')
            # add any discovered keywords for deprecation checker
            YSO_DEPRECATED_MAPS[old_keyword.id] = keyword.id
            print('Mapping events with ' + str(old_keyword) + ' to ' + str(keyword))
            keyword.events.add(*old_keyword.events.all())
            keyword.audience_events.add(*old_keyword.audience_events.all())
        if not getattr(keyword, '_found', False):
            syncher.mark(keyword)
        return keyword
