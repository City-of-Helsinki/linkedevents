from io import StringIO

import pytest
from django.core.management import call_command

from events.tests.factories import DataSourceFactory, KeywordFactory

graph = """
@prefix allars: <http://www.yso.fi/onto/allars/> .
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix isothes: <http://purl.org/iso25964/skos-thes#> .
@prefix koko: <http://www.yso.fi/onto/koko/> .
@prefix lcsh: <http://id.loc.gov/authorities/subjects> .
@prefix ns3: <http://metadataregistry.org/uri/profile/regap/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdau: <http://rdaregistry.info/Elements/u/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix skosext: <http://purl.org/finnonto/schema/skosext#> .
@prefix skosxl: <http://www.w3.org/2008/05/skos-xl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ysa: <http://www.yso.fi/onto/ysa/> .
@prefix yso: <http://www.yso.fi/onto/yso/> .
@prefix yso-meta: <http://www.yso.fi/onto/yso-meta/> .
@prefix ysometa: <http://www.yso.fi/onto/yso-meta/2007-03-02/> .

yso:p29911 a skosext:DeprecatedConcept,
        skos:Concept ;
    dct:created "1996-02-07"^^xsd:date ;
    dct:isReplacedBy yso:p3065 ;
    dct:modified "2018-12-14"^^xsd:date ;
    owl:deprecated true ;
    skos:broadMatch yso:p3065 ;
    skos:closeMatch <http://id.loc.gov/authorities/subjects/sh00000684>,
        allars:Y51875,
        ysa:Y214379 ;
    skos:definition "Yleisnimitys erilaisille afrikkalaisille maailmanmusiikkityyleille."@fi ;
    skos:inScheme yso:deprecatedconceptscheme ;
    skos:prefLabel "Afro"@en,
        "afro"@fi,
        "afro"@sv ;
    skos:relatedMatch yso:p10926,
        yso:p2969,
        yso:p29844,
        yso:p29904,
        yso:p3064,
        yso:p34772 ;
    skos:scopeNote "deprecated on 13.03.2018" ;
    skos:topConceptOf yso:deprecatedconceptscheme ;
    ysometa:deprecatedHasThematicGroup yso:p26571 .
"""


@pytest.mark.django_db
def test_remap_events_without_apply(requests_mock):
    requests_mock.get("http://finto.fi/rest/v1/yso/data", text=graph)
    ds = DataSourceFactory(id="yso")
    replacement = KeywordFactory(id="yso:p3065", data_source=ds)
    replaced = KeywordFactory(
        id="yso:test_replaced", data_source=ds, deprecated=True, replaced_by=replacement
    )
    deprecated_not_replaced = KeywordFactory(
        id="yso:p29911", data_source=ds, deprecated=True
    )

    out = StringIO()
    call_command("check_deprecated_yso_keywords", stdout=out)
    deprecated_not_replaced.refresh_from_db()
    assert deprecated_not_replaced.replaced_by is None

    out = StringIO()
    call_command("check_deprecated_yso_keywords", apply=True, stdout=out)
    deprecated_not_replaced.refresh_from_db()
    assert deprecated_not_replaced.replaced_by == replacement
    assert "1 deprecated keywords without replacements" in out.getvalue()
