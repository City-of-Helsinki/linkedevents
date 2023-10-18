from io import StringIO

import pytest
from django.core.management import call_command

from events.tests.factories import DataSourceFactory, KeywordFactory

graph = """
@prefix dct: <http://purl.org/dc/terms/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix skosext: <http://purl.org/finnonto/schema/skosext#> .
@prefix yso: <http://www.yso.fi/onto/yso/> .
@prefix yso_foo: <http://localhost> .


yso:p29911 a skosext:DeprecatedConcept,
        skos:Concept ;
    dct:isReplacedBy yso:p3065 ;
    owl:deprecated true .
    
yso:test_replacement_not_exists a skosext:DeprecatedConcept,
        skos:Concept ;
    dct:isReplacedBy yso:test_does_not_exist ;
    owl:deprecated true .
    
yso:test_replacement_invalid_yso_id a skosext:DeprecatedConcept,
        skos:Concept ;
    dct:isReplacedBy yso_foo:test_does_not_exist ;
    owl:deprecated true .

yso:test_all_done a skosext:DeprecatedConcept,
        skos:Concept ;
    dct:isReplacedBy yso:p3065 ;
    owl:deprecated true .
    
"""


@pytest.fixture
def requests_mock_graph(requests_mock):
    requests_mock.get("http://finto.fi/rest/v1/yso/data", text=graph)
    return requests_mock


@pytest.fixture
def yso_ds():
    return DataSourceFactory(id="yso")


@pytest.fixture
def kw_deprecated_not_replaced(yso_ds):
    """
    kw that is deprecated
    replacement is missing from db
    replacement defined in graph as yso:p3065
    """
    return KeywordFactory(id="yso:p29911", data_source=yso_ds, deprecated=True)


@pytest.fixture
def kw_replacement_of_deprecated_not_replaced(yso_ds):
    """kw that is the replacement of yso:p29911 according to graph"""
    return KeywordFactory(id="yso:p3065", data_source=yso_ds)


@pytest.fixture
def kw_deprecated_and_replaced(yso_ds, kw_replacement_of_deprecated_not_replaced):
    return KeywordFactory(
        id="yso:test_all_done",
        data_source=yso_ds,
        deprecated=True,
        replaced_by=kw_replacement_of_deprecated_not_replaced,
    )


@pytest.fixture
def kw_deprecated_invalid_replacement(yso_ds):
    """
    kw that is deprecated
    replacement is missing from db
    replacement defined in graph, but does not exist in db
    """
    return KeywordFactory(
        id="yso:test_replacement_not_exists", data_source=yso_ds, deprecated=True
    )


@pytest.fixture
def kw_deprecated_invalid_yso_id(yso_ds):
    """
    kw that is deprecated
    replacement is missing from db
    replacement defined in graph, but does is not in "yso" namespace
    """
    return KeywordFactory(
        id="yso:test_replacement_invalid_yso_id", data_source=yso_ds, deprecated=True
    )


@pytest.mark.django_db
def test_command_dryrun(
    requests_mock_graph,
    kw_deprecated_not_replaced,
    kw_replacement_of_deprecated_not_replaced,
):
    assert kw_deprecated_not_replaced.replaced_by_id is None
    out = StringIO()
    call_command("check_deprecated_yso_keywords", stdout=out)
    kw_deprecated_not_replaced.refresh_from_db()
    assert kw_deprecated_not_replaced.replaced_by is None
    assert "WOULD replace 1 keywords" in out.getvalue()


@pytest.mark.django_db
def test_command_apply(
    requests_mock_graph,
    kw_deprecated_not_replaced,
    kw_replacement_of_deprecated_not_replaced,
):
    out = StringIO()
    call_command("check_deprecated_yso_keywords", apply=True, stdout=out)
    kw_deprecated_not_replaced.refresh_from_db()
    assert (
        kw_deprecated_not_replaced.replaced_by
        == kw_replacement_of_deprecated_not_replaced
    )
    assert "1 deprecated keywords without replacements" in out.getvalue()
    assert "Replaced 1 keywords" in out.getvalue()


@pytest.mark.django_db
def test_command_nothing_to_do(requests_mock_graph, kw_deprecated_and_replaced):
    out = StringIO()
    call_command("check_deprecated_yso_keywords", apply=True, stdout=out)
    assert "No keywords need or can be updated." in out.getvalue()


@pytest.mark.django_db
def test_command_replacement_does_not_exist(
    requests_mock_graph, kw_deprecated_invalid_replacement
):
    out = StringIO()
    call_command("check_deprecated_yso_keywords", apply=True, stdout=out)
    assert "1 replacement keywords do not exist in DB" in out.getvalue()
    assert "No keywords need or can be updated." in out.getvalue()


@pytest.mark.django_db
def test_command_replacement_is_invalid(
    requests_mock_graph, kw_deprecated_invalid_yso_id
):
    out = StringIO()
    call_command("check_deprecated_yso_keywords", apply=True, stdout=out)
    assert "Invalid replacement yso id for 1 keywords" in out.getvalue()
    assert "No keywords need or can be updated." in out.getvalue()


@pytest.mark.django_db
def test_command_replacement_all(
    requests_mock_graph,
    kw_deprecated_and_replaced,
    kw_deprecated_not_replaced,
    kw_deprecated_invalid_yso_id,
    kw_deprecated_invalid_replacement,
):
    out = StringIO()
    call_command("check_deprecated_yso_keywords", apply=True, stdout=out)
    assert "Invalid replacement yso id for 1 keywords" in out.getvalue()
    assert "1 replacement keywords do not exist in DB" in out.getvalue()
    assert "Replaced 1 keywords" in out.getvalue()
