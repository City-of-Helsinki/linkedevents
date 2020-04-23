from distutils import dir_util
import os
import pytest

from events.importer.espoo import EspooImporter, clean_street_address, find_url, YSO_KEYWORD_MAPS
from events.models import DataSource, Keyword


URL = "http://www.lippu.fi/Lippuja.html?doc=artistPages%2Ftickets&fun=artist&action=tickets&xtmc=hetki%C3%A4&xtcr=2"


@pytest.fixture
def datadir(tmpdir, request):
    '''
    Fixture responsible for searching a folder with the same name of test
    module and, if available, moving all contents to a temporary directory so
    tests can use them freely.
    '''
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)

    if os.path.isdir(test_dir):
        dir_util.copy_tree(test_dir, str(tmpdir))

    return tmpdir


@pytest.fixture
def addresses():
    return {
        'Soittoniekanaukio 1 A': {
            'street_address': 'Soittoniekanaukio 1 A',
            'postal_code': '',
            'address_locality': '',
        },
    }


@pytest.fixture
def data_source():
    defaults = dict(name='City of Espoo')
    ds_args = dict(id='espoo')
    data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)
    defaults = dict(name='TPrek')
    ds_args = dict(id='tprek')
    data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)
    defaults = dict(name='YSO')
    ds_args = dict(id='yso')
    data_source, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)


@pytest.fixture
def yso_keyword():
    for kw, ids in YSO_KEYWORD_MAPS.items():
        if not isinstance(ids, tuple):
            ids = (ids,)
        for id_ in ids:
            kwargs = {
                'id': 'yso:%s' % id_,
                'origin_id': id_,
                'data_source_id': 'yso',
                'name': kw,
            }
            keyword = Keyword(**kwargs)
            keyword.save()


@pytest.mark.django_db
def test_address_is_parsed_correctly(addresses):
    for k, v in addresses.items():
        assert clean_street_address(k) == v


@pytest.mark.django_db
def test_keyword_fetch_from_dict(data_source, yso_keyword):
    importer = EspooImporter({'verbosity': True, 'cached': False})
    importer.setup()
    assert importer._map_classification_keywords_from_dict('Teatteri').pop().id == u'yso:p2625'


@pytest.mark.django_db
def test_find_url__extract_url_from_tag():
    tag = "<a href=\"%s\" target=\"_blank\">Lippupiste</a>" % URL
    assert find_url(tag) == URL


@pytest.mark.django_db
def test_find_url__extract_url_from_tag_single_quote():
    """
    Test that url is correctly from an invalid HTML tag which appears in ESPOO API URL
    """
    tag = "<a href='%s' target='_blank'>Lippupiste</a>" % URL
    assert find_url(tag) == URL


@pytest.mark.django_db
def test_find_url__return_url_if_no_tag():
    assert find_url(URL) == URL


@pytest.mark.django_db
def test_find_url__return_url_stripped():
    assert find_url("   %s   " % URL) == URL
